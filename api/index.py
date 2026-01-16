# -*- coding: utf-8 -*-
# Author: ChartWizMani
# Description: "Lite" Version - No Pandas/Matplotlib (Fixes Vercel 500 Error)

import os
import sys
import json
import requests
import tweepy
import zipfile
import io
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Force logs to show up immediately
sys.stdout.reconfigure(line_buffering=True)

# Use Pillow for ALL imaging (Lightweight)
from PIL import Image, ImageDraw, ImageFont

from flask import Flask, jsonify

load_dotenv()
app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "Roboto-Bold.ttf")

COLORS = {
    'bg': (17, 24, 39),       # #111827
    'card_bg': (31, 41, 55),  # #1F2937
    'text': (229, 231, 235),  # #E5E7EB
    'accent': (59, 130, 246), # #3B82F6
    'pos': (16, 185, 129),    # #10B981
    'neg': (244, 63, 94),     # #F43F5E
    'sub': (156, 163, 175)    # #9CA3AF
}

# --- HELPER: FONTS ---
def get_font(size):
    if os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()

# --- HELPER: TWITTER AUTH ---
def get_twitter_api():
    try:
        api_key = os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("TWITTER_API_SECRET")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

        if not all([api_key, api_secret, access_token, access_token_secret]):
            print("❌ Missing Twitter Keys!", flush=True)
            return None

        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        return tweepy.API(auth)
    except Exception as e:
        print(f"❌ Twitter Auth Error: {e}", flush=True)
        return None

# =========================================
# PART 1: GLOBAL MARKET (Standard)
# =========================================
@app.route('/global-market-update')
def global_market_update():
    print("🚀 Starting Global...", flush=True)
    try:
        import yfinance as yf # Lazy load
        yf.set_tz_cache_location("/tmp/yf_tz_cache")
        from bs4 import BeautifulSoup
        
        data = {}
        
        # 1. GIFT Nifty
        try:
            url = "https://groww.in/indices/global-indices/sgx-nifty"
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
            soup = BeautifulSoup(resp.text, 'html.parser')
            raw = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).string)
            price = raw['props']['pageProps']['globalIndicesData']['priceData']
            data["GIFTNIFTY"] = (f"{price['value']:,.2f}", f"{price['dayChangePerc']:+.2f}%")
        except: pass

        # 2. Global Tickers
        tickers = {"Nikkei 225": "^N225", "Dow Futures": "YM=F", "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"}
        for name, sym in tickers.items():
            try:
                hist = yf.Ticker(sym).history(period="5d")
                if len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    chg = ((curr - prev) / prev) * 100
                    data[name] = (f"{curr:,.2f}", f"{chg:+.2f}%")
            except: continue

        # 3. Draw Image (Pillow)
        img = Image.new('RGB', (1080, 1080), color=(20, 20, 40))
        draw = ImageDraw.Draw(img)
        
        draw.text((540, 150), "Global Market Update", font=get_font(78), fill="white", anchor="mm")
        draw.text((540, 230), datetime.now().strftime("%d %b, %Y"), font=get_font(48), fill=COLORS['sub'], anchor="mm")

        y = 360
        for k in ["GIFTNIFTY", "Nikkei 225", "Dow Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
            v, c = data.get(k, ("N/A", "0%"))
            col = (255, 80, 80) if c.startswith('-') else (80, 255, 80)
            draw.text((100, y), f"{k}:", font=get_font(42), fill="white", anchor="lm")
            draw.text((750, y), v, font=get_font(42), fill="white", anchor="rm")
            draw.text((980, y), c, font=get_font(42), fill=col, anchor="rm")
            y += 100
            
        draw.text((540, 1030), "@ChartWizMani | Data as of Today", font=get_font(28), fill=COLORS['sub'], anchor="mm")
        
        filename = "/tmp/global_update.png"
        img.save(filename)

        # 4. Post
        api = get_twitter_api()
        if api:
            txt = [f"Global Market Update – {datetime.now().strftime('%d %b')}\n"]
            for k, (v, c) in data.items(): txt.append(f"{k}: {v} ({c})")
            txt.append("\n#StockMarket #Nifty")
            media = api.media_upload(filename)
            api.update_status(status="\n".join(txt), media_ids=[media.media_id])
            
        return jsonify({"status": "posted"}), 200
    except Exception as e:
        print(f"Global Error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

# =========================================
# PART 2: MTF INSIGHTS (The Lite Engine)
# =========================================
@app.route('/mtf-insights-update')
def mtf_insights_update():
    print("🚀 Starting MTF (Lite)...", flush=True)
    try:
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nseindia.com/'})
        try: session.get("https://www.nseindia.com/", timeout=2)
        except: pass

        mtf_data = None
        
        # 1. Fetch CSV (No Pandas)
        for days_ago in range(3):
            target_date = datetime.now() - timedelta(days=days_ago)
            date_url = target_date.strftime("%d%m%y")
            url = f"https://nsearchives.nseindia.com/content/equities/mrg_trading_{date_url}.zip"
            
            print(f"   Checking {url}...", flush=True)
            try:
                resp = session.get(url, timeout=3)
                if resp.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                        csv_name = [f for f in z.namelist() if f.lower().endswith('.csv')][0]
                        with z.open(csv_name) as f:
                            # Read lines as text
                            lines = f.read().decode('utf-8', errors='ignore').splitlines()
                            
                            # A. Parse Summary (Top 20 lines)
                            added = 0.0; liquidated = 0.0; book = 0.0
                            for line in lines[:20]:
                                if "Fresh Exposure" in line: added = float(line.split(',')[2].replace(',', ''))/100
                                if "Exposure liquidated" in line: liquidated = float(line.split(',')[2].replace(',', ''))/100
                                if "Net scripwise" in line: book = float(line.split(',')[2].replace(',', ''))/100
                            
                            # B. Parse Details (Find Header)
                            header_idx = -1
                            for i, line in enumerate(lines):
                                if "Symbol" in line and "Qty" in line:
                                    header_idx = i; break
                            
                            top_val = []; top_vol = []
                            if header_idx != -1:
                                # Parse CSV manually (Symbol is col 0, Amt is last col usually)
                                # We need to be careful with column indices. 
                                # Header: Symbol, Name, Qty, Amt
                                reader = csv.reader(lines[header_idx+1:])
                                rows = []
                                for row in reader:
                                    if len(row) < 4: continue
                                    try:
                                        sym = row[0]
                                        qty = float(row[2])
                                        amt = float(row[3])
                                        rows.append({'sym': sym, 'qty': qty, 'amt': amt})
                                    except: continue
                                
                                # Sort by Value
                                rows.sort(key=lambda x: x['amt'], reverse=True)
                                top_val = [(r['sym'], r['amt']/100) for r in rows[:10]]
                                
                                # Sort by Volume
                                rows.sort(key=lambda x: x['qty'], reverse=True)
                                top_vol = [(r['sym'], r['qty']) for r in rows[:10]]

                            mtf_data = {
                                'date': target_date.strftime("%d-%b-%Y"),
                                'added': added, 'liquidated': liquidated,
                                'net': added - liquidated, 'book': book,
                                'top_val': top_val, 'top_vol': top_vol
                            }
                    break # Success
            except Exception as e:
                print(f"   Skip {date_url}: {e}", flush=True)
                continue

        if not mtf_data:
            return jsonify({"error": "No data found"}), 500

        # 2. Draw Dashboard (Pillow - mimicking Matplotlib)
        print("   Drawing Chart...", flush=True)
        W, H = 1600, 900
        img = Image.new('RGB', (W, H), color=COLORS['bg'])
        draw = ImageDraw.Draw(img)

        # Header
        draw.text((50, 50), "MTF Market Insights", font=get_font(60), fill="white")
        draw.text((50, 130), f"Margin Trading Funding Analysis | {mtf_data['date']}", font=get_font(30), fill=COLORS['sub'])

        # KPI Cards (Manual Drawing)
        cards = [
            ("Added", f"₹{mtf_data['added']:,.0f} Cr", COLORS['pos']),
            ("Liquidated", f"₹{mtf_data['liquidated']:,.0f} Cr", COLORS['neg']),
            ("Net Flow", f"{'+' if mtf_data['net']>=0 else ''}₹{mtf_data['net']:,.0f} Cr", COLORS['pos'] if mtf_data['net']>=0 else COLORS['neg']),
            ("Total Book", f"₹{mtf_data['book']:,.0f} Cr", COLORS['accent'])
        ]
        
        card_w, card_h = 350, 200
        start_x, start_y = 50, 220
        gap = 40
        
        for i, (title, val, col) in enumerate(cards):
            x = start_x + i * (card_w + gap)
            draw.rectangle([x, start_y, x+card_w, start_y+card_h], fill=COLORS['card_bg'], outline=None)
            draw.text((x + card_w/2, start_y + 40), title, font=get_font(28), fill=COLORS['sub'], anchor="mm")
            draw.text((x + card_w/2, start_y + 120), val, font=get_font(48), fill=col, anchor="mm")

        # Tables
        def draw_list_box(title, items, x_pos, is_vol):
            draw.text((x_pos, 500), title, font=get_font(32), fill=COLORS['accent'])
            y = 560
            for idx, (sym, val) in enumerate(items):
                bg = COLORS['card_bg'] if idx % 2 == 0 else COLORS['bg']
                draw.rectangle([x_pos, y, x_pos+700, y+50], fill=bg)
                
                val_str = f"{val/1e6:.1f}M" if is_vol and val>1e6 else (f"{val/1e3:.0f}K" if is_vol else f"₹{val:,.1f} Cr")
                col = COLORS['accent'] if is_vol else COLORS['pos']
                
                draw.text((x_pos+20, y+25), f"{idx+1}. {sym}", font=get_font(28), fill=COLORS['text'], anchor="lm")
                draw.text((x_pos+680, y+25), val_str, font=get_font(28), fill=col, anchor="rm")
                y += 55

        draw_list_box("Top 10 Additions (Value)", mtf_data['top_val'], 50, False)
        draw_list_box("Top 10 Volume Buzzers", mtf_data['top_vol'], 850, True)

        draw.text((W-50, H-50), f"@ChartWizMani | {mtf_data['date']}", font=get_font(24), fill=COLORS['sub'], anchor="rm")
        
        filename = "/tmp/mtf_lite.png"
        img.save(filename)

        # 3. Post
        api = get_twitter_api()
        if api:
            sign = "+" if mtf_data['net'] >= 0 else ""
            txt = (f"MTF Insights | {mtf_data['date']}\n\n"
                   f"Added: ₹{mtf_data['added']:,.0f} Cr\n"
                   f"Liquidated: ₹{mtf_data['liquidated']:,.0f} Cr\n"
                   f"Net: {sign}₹{mtf_data['net']:,.0f} Cr\n"
                   f"Total Book: ₹{mtf_data['book']:,.0f} Cr\n\n#MTF #Nifty")
            media = api.media_upload(filename)
            api.update_status(status=txt, media_ids=[media.media_id])
            
        return jsonify({"status": "posted", "date": mtf_data['date']}), 200

    except Exception as e:
        print(f"❌ MTF Error: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home(): return "Tweet Bot Lite (Vercel Optimized) Running"
