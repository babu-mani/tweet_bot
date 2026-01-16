# -*- coding: utf-8 -*-
# Author: ChartWizMani
# Description: Generates and posts financial market updates (Global & MTF) to Twitter.
# Vercel-Ready: Uses /tmp for storage and headless Matplotlib.

from flask import Flask, jsonify
import os
import sys
import json
import requests
import tweepy
import yfinance as yf
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont # For Global Market Image
from dotenv import load_dotenv
import zipfile
import io
import pandas as pd

# --- MATPLOTLIB SETUP (Must be before pyplot import) ---
import matplotlib
matplotlib.use('Agg') # Force headless mode for Vercel
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as patches

# --- SERVERLESS CONFIG ---
load_dotenv()
yf.set_tz_cache_location("/tmp/yf_tz_cache") # Fix for Vercel Read-Only FS

app = Flask(__name__)

# --- FONTS CONFIGURATION ---
# We use the existing Roboto-Bold.ttf for everything to keep it simple
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "Roboto-Bold.ttf")

# --- STYLING CONSTANTS (MTF) ---
COLORS = {
    'bg': '#111827', 'card_bg': '#1F2937', 'title': '#F9FAFB',
    'subtitle': '#9CA3AF', 'text': '#E5E7EB', 'accent': '#3B82F6',
    'positive': '#10B981', 'negative': '#F43F5E', 'bright_text': '#F3F4F6'
}

# --- HELPER: TWITTER AUTH ---
def get_twitter_api():
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("❌ Missing Twitter API Credentials")
        return None

    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    return tweepy.API(auth)

# =========================================
# PART 1: GLOBAL MARKET FUNCTIONS (Existing)
# =========================================

def get_pil_font(size):
    """Helper for Pillow fonts (Global Market)"""
    if not os.path.exists(FONT_PATH):
        return ImageFont.load_default()
    return ImageFont.truetype(FONT_PATH, size)

def fetch_gift_nifty():
    try:
        url = "https://groww.in/indices/global-indices/sgx-nifty"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        data = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).string)
        price_data = data['props']['pageProps']['globalIndicesData']['priceData']
        return f"{price_data['value']:,.2f}", f"{price_data['dayChangePerc']:+.2f}%"
    except Exception as e:
        print(f"GIFT NIFTY Error: {e}")
        return None, None

def get_yfinance_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1mo")
        hist = hist.dropna()
        if len(hist) < 2: return None, None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        chg = ((curr - prev) / prev) * 100
        return f"{curr:,.2f}", f"{chg:+.2f}%"
    except:
        return None, None

def fetch_global_data():
    data = {}
    gn_val, gn_chg = fetch_gift_nifty()
    if gn_val: data["GIFTNIFTY"] = (gn_val, gn_chg)
    
    tickers = {
        "Nikkei 225": "^N225", "Dow Futures": "YM=F",
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"
    }
    for name, sym in tickers.items():
        val, chg = get_yfinance_data(sym)
        if val: data[name] = (val, chg)
    return data

def create_global_image(data):
    width, height = 1080, 1080
    img = Image.new('RGB', (width, height), color=(20, 20, 40))
    draw = ImageDraw.Draw(img)
    
    # Draw logic
    draw.text((width/2, 150), "Global Market Update", font=get_pil_font(78), fill=(255,255,255), anchor="mm")
    draw.text((width/2, 230), datetime.now().strftime("%d %b, %Y"), font=get_pil_font(48), fill=(180,180,200), anchor="mm")

    y_pos = 360
    for key in ["GIFTNIFTY", "Nikkei 225", "Dow Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
        val, chg = data.get(key, ("N/A", "+0.00%"))
        col = (255, 80, 80) if chg.startswith('-') else (80, 255, 80)
        draw.text((100, y_pos), f"{key}:", font=get_pil_font(42), fill=(255,255,255), anchor="lm")
        draw.text((750, y_pos), val, font=get_pil_font(42), fill=(255,255,255), anchor="rm")
        draw.text((width-100, y_pos), chg, font=get_pil_font(42), fill=col, anchor="rm")
        y_pos += 100

    # Watermark
    draw.text((width/2, height-50), "@ChartWizMani | Data as of " + datetime.now().strftime('%d-%b-%Y'), font=get_pil_font(28), fill=(180,180,200), anchor="mm")
    
    filename = "/tmp/global_update.png"
    img.save(filename)
    return filename

# =========================================
# PART 2: MTF FUNCTIONS (New & Robust)
# =========================================

def get_mpl_font_props():
    """Helper for Matplotlib fonts (Uses Roboto-Bold.ttf)"""
    try:
        return fm.FontProperties(fname=FONT_PATH) if os.path.exists(FONT_PATH) else fm.FontProperties()
    except:
        return fm.FontProperties()

def fetch_mtf_robust():
    """Loops back 7 days to find the latest valid NSE MTF report"""
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nseindia.com/'})
    
    # Prime session
    try: session.get("https://www.nseindia.com/", timeout=3)
    except: pass

    for days_ago in range(7):
        target_date = datetime.now() - timedelta(days=days_ago)
        date_url = target_date.strftime("%d%m%y")
        date_display = target_date.strftime("%d-%b-%Y")
        url = f"https://nsearchives.nseindia.com/content/equities/mrg_trading_{date_url}.zip"

        try:
            print(f"Checking MTF for {date_display}...")
            resp = session.get(url, timeout=10)
            if resp.status_code == 404: continue
            
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                csv_name = [f for f in z.namelist() if f.lower().endswith('.csv')][0]
                with z.open(csv_name) as f:
                    content = f.read()
                    
                    # 1. Parse Summary
                    df_sum = pd.read_csv(io.BytesIO(content), header=None, nrows=20)
                    def get_val(k):
                        row = df_sum[df_sum[1].str.contains(k, na=False, case=False)]
                        return float(str(row.iloc[0,2]).replace(',','').strip())/100 if not row.empty else 0.0
                    
                    data = {
                        'date': date_display,
                        'added': get_val("Fresh Exposure"),
                        'liquidated': get_val("Exposure liquidated"),
                        'industry_book': get_val("Net scripwise outstanding")
                    }
                    data['net'] = data['added'] - data['liquidated']

                    # 2. Parse Top 10s
                    csv_lines = content.decode('utf-8', errors='ignore').splitlines()
                    header_idx = next((i for i, l in enumerate(csv_lines) if "Symbol" in l and "Qty" in l), -1)
                    
                    data['top_val'], data['top_vol'] = [], []
                    if header_idx != -1:
                        df = pd.read_csv(io.BytesIO(content), skiprows=header_idx)
                        df.columns = [c.strip() for c in df.columns]
                        # Robust column finding
                        col_sym = next((c for c in df.columns if "Symbol" in c), "Symbol")
                        col_amt = next((c for c in df.columns if "Amt" in c and "Fin" in c), None)
                        col_qty = next((c for c in df.columns if "Qty" in c and "Fin" in c), None)
                        
                        if col_amt:
                            for _, r in df.sort_values(by=col_amt, ascending=False).head(10).iterrows():
                                data['top_val'].append((r[col_sym], r[col_amt]/100))
                        if col_qty:
                            for _, r in df.sort_values(by=col_qty, ascending=False).head(10).iterrows():
                                data['top_vol'].append((r[col_sym], r[col_qty]))
            
            return data # Success
        except Exception as e:
            print(f"Error parsing {date_display}: {e}")
            continue
            
    return None

def create_mtf_image(data):
    # Setup
    fig = plt.figure(figsize=(16, 9), facecolor=COLORS['bg'])
    ax = fig.add_axes([0,0,1,1]); ax.axis('off')
    
    # Use existing Roboto font
    font_main = get_mpl_font_props()
    
    # Header
    fig.text(0.05, 0.92, "MTF Market Insights", fontproperties=font_main, fontsize=36, color=COLORS['title'])
    fig.text(0.05, 0.88, f"Margin Trading Funding Analysis | {data['date']}", fontproperties=font_main, fontsize=16, color=COLORS['subtitle'])
    
    # KPI Cards
    kpis = [
        ("Positions Added", f"₹{data['added']:,.0f} Cr", COLORS['positive']),
        ("Positions Liquidated", f"₹{data['liquidated']:,.0f} Cr", COLORS['negative']),
        ("Net Book Added", f"{'+' if data['net']>=0 else ''}₹{data['net']:,.0f} Cr", COLORS['positive'] if data['net']>=0 else COLORS['negative']),
        ("Total Industry Book", f"₹{data['industry_book']:,.0f} Cr", COLORS['accent'])
    ]
    
    card_y, card_w, card_h, gap = 0.68, 0.20, 0.15, 0.03
    for i, (title, val, col) in enumerate(kpis):
        x = 0.05 + i*(card_w + gap)
        ax.add_patch(patches.FancyBboxPatch((x, card_y), card_w, card_h, boxstyle="round,pad=0.02", fc=COLORS['card_bg'], ec='none'))
        fig.text(x + card_w/2, card_y + card_h - 0.04, title, ha='center', fontproperties=font_main, fontsize=14, color=COLORS['subtitle'])
        fig.text(x + card_w/2, card_y + 0.05, val, ha='center', fontproperties=font_main, fontsize=24, color=col)

    # Tables
    def draw_list(title, items, x_pos, is_vol):
        fig.text(x_pos, 0.60, title, fontproperties=font_main, fontsize=18, color=COLORS['accent'])
        y = 0.54
        for idx, (sym, val) in enumerate(items):
            bg = COLORS['card_bg'] if idx % 2 == 0 else COLORS['bg']
            ax.add_patch(patches.Rectangle((x_pos, y-0.01), 0.40, 0.045, fc=bg))
            val_str = f"{val/1e6:.1f}M" if is_vol and val > 1e6 else (f"{val/1e3:.0f}K" if is_vol else f"₹{val:,.1f} Cr")
            col = COLORS['accent'] if is_vol else COLORS['positive']
            
            fig.text(x_pos+0.02, y+0.01, f"{idx+1}. {sym}", fontproperties=font_main, fontsize=15, color=COLORS['text'])
            fig.text(x_pos+0.38, y+0.01, val_str, fontproperties=font_main, fontsize=15, color=col, ha='right')
            y -= 0.05

    draw_list("Top 10 Additions (Value)", data.get('top_val', []), 0.05, False)
    draw_list("Top 10 Volume Buzzers", data.get('top_vol', []), 0.52, True)

    # Watermark
    fig.text(0.98, 0.02, f"@ChartWizMani | Data as of {data['date']}", ha='right', fontproperties=font_main, fontsize=12, color=COLORS['subtitle'])

    filename = "/tmp/mtf_insights.png"
    plt.savefig(filename, dpi=100, facecolor=COLORS['bg'])
    plt.close()
    return filename

# =========================================
# ROUTES
# =========================================

@app.route('/global-market-update')
def global_market_update():
    try:
        data = fetch_global_data()
        if not data: return jsonify({"status": "error"}), 500
        
        img_path = create_global_image(data)
        
        # Build Tweet
        txt = [f"Global Market Update – {datetime.now().strftime('%d %b')}\n"]
        for k in ["GIFTNIFTY", "Nikkei 225", "Dow Futures", "S&P 500", "Nasdaq"]:
            v, c = data.get(k, ("N/A", "0%"))
            txt.append(f"{k}: {v} ({c})")
        txt.append("\n#StockMarket #Nifty #GIFTNIFTY")
        
        # Post
        api = get_twitter_api()
        if api:
            media = api.media_upload(img_path)
            api.update_status(status="\n".join(txt), media_ids=[media.media_id])
            
        return jsonify({"status": "posted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mtf-insights-update')
def mtf_insights_update():
    try:
        data = fetch_mtf_robust()
        if not data: return jsonify({"status": "error", "message": "No MTF data found in last 7 days"}), 500
        
        img_path = create_mtf_image(data)
        
        # Build Tweet
        sign = "+" if data['net'] >= 0 else ""
        txt = (
            f"MTF Insights | {data['date']}\n\n"
            f"🔹 Added: ₹{data['added']:,.0f} Cr\n"
            f"🔻 Liquidated: ₹{data['liquidated']:,.0f} Cr\n"
            f"📊 Net Flow: {sign}₹{data['net']:,.0f} Cr\n\n"
            f"📚 Total Book: ₹{data['industry_book']:,.0f} Cr\n\n"
            f"#MTF #StockMarketIndia #Nifty #Trading"
        )
        
        # Post
        api = get_twitter_api()
        if api:
            media = api.media_upload(img_path)
            api.update_status(status=txt, media_ids=[media.media_id])
            
        return jsonify({"status": "posted", "date": data['date']}), 200
    except Exception as e:
        print(f"MTF Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Tweet Bot is Running!"
