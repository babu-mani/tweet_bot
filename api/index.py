# -*- coding: utf-8 -*-
# Author: ChartWizMani
# Description: Ultra-Stable Vercel Version with Force-Logging

# --- 1. CRITICAL SETUP (Must be first) ---
import os
import sys

# Force immediate log flushing (Fixes missing logs)
sys.stdout.reconfigure(line_buffering=True)

# Set environment variables BEFORE importing heavy libraries
os.environ['MPLCONFIGDIR'] = '/tmp'
os.environ['HOME'] = '/tmp'

from flask import Flask, jsonify
import json
import requests
import tweepy
import zipfile
import io
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- 2. LAZY LOAD HEAVY LIBS ---
# We do not import pandas/matplotlib/yfinance at the top level.
# They are imported inside functions to prevent "Cold Start" timeouts.

load_dotenv()
app = Flask(__name__)

# --- HELPER: TWITTER AUTH ---
def get_twitter_api():
    print("🔑 Authenticating Twitter...", flush=True)
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
        print(f"❌ Auth Error: {e}", flush=True)
        return None

# =========================================
# ROUTE 1: GLOBAL MARKET
# =========================================
@app.route('/global-market-update')
def global_market_update():
    print("🚀 Starting Global Market Update...", flush=True)
    try:
        # Lazy Imports
        import yfinance as yf
        from bs4 import BeautifulSoup
        from PIL import Image, ImageDraw, ImageFont 
        
        yf.set_tz_cache_location("/tmp/yf_tz_cache")

        data = {}
        
        # 1. GIFT Nifty
        try:
            print("   Fetching GIFT Nifty...", flush=True)
            url = "https://groww.in/indices/global-indices/sgx-nifty"
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
            soup = BeautifulSoup(resp.text, 'html.parser')
            raw = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).string)
            price = raw['props']['pageProps']['globalIndicesData']['priceData']
            data["GIFTNIFTY"] = (f"{price['value']:,.2f}", f"{price['dayChangePerc']:+.2f}%")
        except Exception as e:
            print(f"   ⚠️ GIFT Nifty Failed: {e}", flush=True)

        # 2. Global Indices
        tickers = {
            "Nikkei 225": "^N225", "Dow Futures": "YM=F",
            "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"
        }
        
        print("   Fetching Global Tickers...", flush=True)
        for name, sym in tickers.items():
            try:
                hist = yf.Ticker(sym).history(period="5d")
                if len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    chg = ((curr - prev) / prev) * 100
                    data[name] = (f"{curr:,.2f}", f"{chg:+.2f}%")
            except:
                continue

        if not data:
            print("❌ No Global Data Found!", flush=True)
            return jsonify({"status": "error", "message": "No data fetched"}), 500

        # 3. Image Gen
        print("   Generating Image...", flush=True)
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        FONT_PATH = os.path.join(BASE_DIR, "Roboto-Bold.ttf") # Assumes flat structure
        
        def get_font(size):
            return ImageFont.truetype(FONT_PATH, size) if os.path.exists(FONT_PATH) else ImageFont.load_default()

        width, height = 1080, 1080
        img = Image.new('RGB', (width, height), color=(20, 20, 40))
        draw = ImageDraw.Draw(img)
        
        draw.text((width/2, 150), "Global Market Update", font=get_font(78), fill=(255,255,255), anchor="mm")
        draw.text((width/2, 230), datetime.now().strftime("%d %b, %Y"), font=get_font(48), fill=(180,180,200), anchor="mm")

        y_pos = 360
        for key in ["GIFTNIFTY", "Nikkei 225", "Dow Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
            val, chg = data.get(key, ("N/A", "0%"))
            col = (255, 80, 80) if chg.startswith('-') else (80, 255, 80)
            draw.text((100, y_pos), f"{key}:", font=get_font(42), fill=(255,255,255), anchor="lm")
            draw.text((750, y_pos), val, font=get_font(42), fill=(255,255,255), anchor="rm")
            draw.text((width-100, y_pos), chg, font=get_font(42), fill=col, anchor="rm")
            y_pos += 100

        draw.text((width/2, height-50), "@ChartWizMani | Data as of " + datetime.now().strftime('%d-%b-%Y'), font=get_font(28), fill=(180,180,200), anchor="mm")
        
        filename = "/tmp/global_update.png"
        img.save(filename)

        # 4. Post
        print("   Posting to Twitter...", flush=True)
        api = get_twitter_api()
        if api:
            txt = [f"Global Market Update – {datetime.now().strftime('%d %b')}\n"]
            for k, (v, c) in data.items():
                txt.append(f"{k}: {v} ({c})")
            txt.append("\n#StockMarket #Nifty #GIFTNIFTY")
            media = api.media_upload(filename)
            api.update_status(status="\n".join(txt), media_ids=[media.media_id])
            print("✅ Global Update Posted!", flush=True)

        return jsonify({"status": "posted"}), 200

    except Exception as e:
        print(f"❌ CRITICAL GLOBAL ERROR: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

# =========================================
# ROUTE 2: MTF INSIGHTS
# =========================================
@app.route('/mtf-insights-update')
def mtf_insights_update():
    print("🚀 Starting MTF Insights...", flush=True)
    try:
        # Lazy Imports
        print("   Importing Libs...", flush=True)
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import matplotlib.patches as patches

        # Data Fetch
        print("   Fetching NSE Data...", flush=True)
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nseindia.com/'})
        
        # Prime session
        try: session.get("https://www.nseindia.com/", timeout=2)
        except: pass

        data = None
        # Loop only 3 days back for speed
        for days_ago in range(3): 
            target_date = datetime.now() - timedelta(days=days_ago)
            date_str = target_date.strftime("%d%m%y")
            url = f"https://nsearchives.nseindia.com/content/equities/mrg_trading_{date_str}.zip"
            
            print(f"   Checking: {url}", flush=True)
            try:
                resp = session.get(url, timeout=3)
                if resp.status_code == 200:
                    print("   ✅ Found Data! Processing...", flush=True)
                    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                        csv_name = [f for f in z.namelist() if f.lower().endswith('.csv')][0]
                        with z.open(csv_name) as f:
                            content = f.read()
                            
                            # Summary
                            df_sum = pd.read_csv(io.BytesIO(content), header=None, nrows=20)
                            def get_val(k):
                                row = df_sum[df_sum[1].str.contains(k, na=False, case=False)]
                                return float(str(row.iloc[0,2]).replace(',','').strip())/100 if not row.empty else 0.0
                            
                            data = {
                                'date': target_date.strftime("%d-%b-%Y"),
                                'added': get_val("Fresh Exposure"),
                                'liquidated': get_val("Exposure liquidated"),
                                'industry_book': get_val("Net scripwise outstanding")
                            }
                            data['net'] = data['added'] - data['liquidated']

                            # Details
                            csv_lines = content.decode('utf-8', errors='ignore').splitlines()
                            header_idx = next((i for i, l in enumerate(csv_lines) if "Symbol" in l and "Qty" in l), -1)
                            
                            data['top_val'], data['top_vol'] = [], []
                            if header_idx != -1:
                                df = pd.read_csv(io.BytesIO(content), skiprows=header_idx)
                                df.columns = [c.strip() for c in df.columns]
                                col_amt = next((c for c in df.columns if "Amt" in c and "Fin" in c), None)
                                col_qty = next((c for c in df.columns if "Qty" in c and "Fin" in c), None)
                                col_sym = next((c for c in df.columns if "Symbol" in c), "Symbol")
                                
                                if col_amt:
                                    for _, r in df.sort_values(by=col_amt, ascending=False).head(10).iterrows():
                                        data['top_val'].append((r[col_sym], r[col_amt]/100))
                                if col_qty:
                                    for _, r in df.sort_values(by=col_qty, ascending=False).head(10).iterrows():
                                        data['top_vol'].append((r[col_sym], r[col_qty]))
                    break # Success
            except Exception as e:
                print(f"   ⚠️ Fetch/Parse Error: {e}", flush=True)
                continue
        
        if not data:
            print("❌ No MTF Data Found (Last 3 Days)", flush=True)
            return jsonify({"error": "No data found"}), 500

        # Image Gen
        print("   Generating Chart...", flush=True)
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        FONT_PATH = os.path.join(BASE_DIR, "Roboto-Bold.ttf")
        
        def get_mpl_font():
            return fm.FontProperties(fname=FONT_PATH) if os.path.exists(FONT_PATH) else fm.FontProperties()

        COLORS = {'bg': '#111827', 'card_bg': '#1F2937', 'text': '#E5E7EB', 'accent': '#3B82F6', 'pos': '#10B981', 'neg': '#F43F5E'}
        fig = plt.figure(figsize=(16, 9), facecolor=COLORS['bg'])
        ax = fig.add_axes([0,0,1,1]); ax.axis('off')
        font_main = get_mpl_font()
        
        fig.text(0.05, 0.92, "MTF Market Insights", fontproperties=font_main, fontsize=36, color='#F9FAFB')
        fig.text(0.05, 0.88, f"Analysis | {data['date']}", fontproperties=font_main, fontsize=16, color='#9CA3AF')

        kpis = [("Added", f"₹{data['added']:,.0f} Cr", COLORS['pos']), ("Liquidated", f"₹{data['liquidated']:,.0f} Cr", COLORS['neg']),
                ("Net Flow", f"{'+' if data['net']>=0 else ''}₹{data['net']:,.0f} Cr", COLORS['pos'] if data['net']>=0 else COLORS['neg']),
                ("Total Book", f"₹{data['industry_book']:,.0f} Cr", COLORS['accent'])]
        
        for i, (t, v, c) in enumerate(kpis):
            x = 0.05 + i*0.23
            ax.add_patch(patches.FancyBboxPatch((x, 0.68), 0.20, 0.15, boxstyle="round,pad=0.02", fc=COLORS['card_bg'], ec='none'))
            fig.text(x+0.1, 0.79, t, ha='center', fontproperties=font_main, fontsize=14, color='#9CA3AF')
            fig.text(x+0.1, 0.73, v, ha='center', fontproperties=font_main, fontsize=24, color=c)

        def draw_list(t, items, x_pos, is_vol):
            fig.text(x_pos, 0.60, t, fontproperties=font_main, fontsize=18, color=COLORS['accent'])
            y = 0.54
            for idx, (sym, val) in enumerate(items):
                ax.add_patch(patches.Rectangle((x_pos, y-0.01), 0.40, 0.045, fc=(COLORS['card_bg'] if idx%2==0 else COLORS['bg'])))
                val_str = f"{val/1e6:.1f}M" if is_vol and val>1e6 else (f"{val/1e3:.0f}K" if is_vol else f"₹{val:,.1f} Cr")
                col = COLORS['accent'] if is_vol else COLORS['pos']
                fig.text(x_pos+0.02, y+0.01, f"{idx+1}. {sym}", fontproperties=font_main, fontsize=15, color=COLORS['text'])
                fig.text(x_pos+0.38, y+0.01, val_str, fontproperties=font_main, fontsize=15, color=col, ha='right')
                y -= 0.05

        draw_list("Top 10 Additions (Value)", data['top_val'], 0.05, False)
        draw_list("Top 10 Volume Buzzers", data['top_vol'], 0.52, True)
        
        fig.text(0.98, 0.02, f"@ChartWizMani | {data['date']}", ha='right', fontproperties=font_main, fontsize=12, color='#9CA3AF')
        
        filename = "/tmp/mtf_insights.png"
        plt.savefig(filename, dpi=100, facecolor=COLORS['bg'])
        plt.close()

        # Post
        print("   Posting to Twitter...", flush=True)
        api = get_twitter_api()
        if api:
            sign = "+" if data['net'] >= 0 else ""
            txt = (f"MTF Insights | {data['date']}\n\nAdded: ₹{data['added']:,.0f} Cr\nLiquidated: ₹{data['liquidated']:,.0f} Cr\n"
                   f"Net: {sign}₹{data['net']:,.0f} Cr\nTotal Book: ₹{data['industry_book']:,.0f} Cr\n\n#MTF #Nifty")
            media = api.media_upload(filename)
            api.update_status(status=txt, media_ids=[media.media_id])
            print("✅ MTF Tweet Posted!", flush=True)

        return jsonify({"status": "posted", "date": data['date']}), 200

    except Exception as e:
        print(f"❌ CRITICAL MTF ERROR: {e}", flush=True)
        # Import traceback to see exactly where it crashed
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Tweet Bot is Stable & Running!"
