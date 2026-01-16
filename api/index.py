# -*- coding: utf-8 -*-
# Author: ChartWizMani
# Description: Speed-Optimized for Vercel 10s Timeout (Lazy Loading)

from flask import Flask, jsonify
import os
import sys
import json
import requests
import tweepy
from datetime import datetime, timedelta
from dotenv import load_dotenv
import zipfile
import io

# --- SERVERLESS CONFIG ---
load_dotenv()
app = Flask(__name__)

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
# PART 1: GLOBAL MARKET (Optimized)
# =========================================
@app.route('/global-market-update')
def global_market_update():
    try:
        # --- LAZY IMPORTS (Saves ~2-3s on startup) ---
        import yfinance as yf
        from bs4 import BeautifulSoup
        from PIL import Image, ImageDraw, ImageFont 
        
        # Configure yfinance cache
        yf.set_tz_cache_location("/tmp/yf_tz_cache")

        # --- DATA FETCHING ---
        data = {}
        
        # 1. GIFT Nifty (Fast Timeout)
        try:
            url = "https://groww.in/indices/global-indices/sgx-nifty"
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=3) # Strict 3s timeout
            soup = BeautifulSoup(resp.text, 'html.parser')
            raw = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).string)
            price = raw['props']['pageProps']['globalIndicesData']['priceData']
            data["GIFTNIFTY"] = (f"{price['value']:,.2f}", f"{price['dayChangePerc']:+.2f}%")
        except:
            pass # Skip if slow

        # 2. YFinance (Batch where possible or sequential)
        tickers = {
            "Nikkei 225": "^N225", "Dow Futures": "YM=F",
            "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"
        }
        
        for name, sym in tickers.items():
            try:
                # Fetch minimal history (2 days)
                hist = yf.Ticker(sym).history(period="5d")
                if len(hist) >= 2:
                    curr = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    chg = ((curr - prev) / prev) * 100
                    data[name] = (f"{curr:,.2f}", f"{chg:+.2f}%")
            except:
                continue

        if not data: return jsonify({"status": "error", "message": "No data fetched"}), 500

        # --- IMAGE GENERATION ---
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        FONT_PATH = os.path.join(BASE_DIR, "fonts", "Roboto-Bold.ttf")
        
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

        # --- TWITTER POST ---
        api = get_twitter_api()
        if api:
            txt = [f"Global Market Update – {datetime.now().strftime('%d %b')}\n"]
            for k, (v, c) in data.items():
                txt.append(f"{k}: {v} ({c})")
            txt.append("\n#StockMarket #Nifty #GIFTNIFTY")
            media = api.media_upload(filename)
            api.update_status(status="\n".join(txt), media_ids=[media.media_id])

        return jsonify({"status": "posted"}), 200

    except Exception as e:
        print(f"Global Error: {e}")
        return jsonify({"error": str(e)}), 500

# =========================================
# PART 2: MTF INSIGHTS (Optimized)
# =========================================
@app.route('/mtf-insights-update')
def mtf_insights_update():
    try:
        # --- LAZY IMPORTS (Saves ~3s on startup) ---
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg') # Headless
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import matplotlib.patches as patches
        
        # Force cache to /tmp
        os.environ['MPLCONFIGDIR'] = '/tmp'

        # --- DATA FETCHING (Reduced Loop) ---
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.nseindia.com/'})
        
        data = None
        # REDUCED LOOP: Check only last 3 days to avoid timeout
        for days_ago in range(3): 
            target_date = datetime.now() - timedelta(days=days_ago)
            date_url = target_date.strftime("%d%m%y")
            url = f"https://nsearchives.nseindia.com/content/equities/mrg_trading_{date_url}.zip"

            try:
                # STRICT 2s TIMEOUT
                resp = session.get(url, timeout=2) 
                if resp.status_code == 404: continue
                
                with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                    csv_name = [f for f in z.namelist() if f.lower().endswith('.csv')][0]
                    with z.open(csv_name) as f:
                        content = f.read()
                        
                        # Parse Summary
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

                        # Parse Top 10s
                        csv_lines = content.decode('utf-8', errors='ignore').splitlines()
                        header_idx = next((i for i, l in enumerate(csv_lines) if "Symbol" in l and "Qty" in l), -1)
                        data['top_val'], data['top_vol'] = [], []
                        
                        if header_idx != -1:
                            df = pd.read_csv(io.BytesIO(content), skiprows=header_idx)
                            df.columns = [c.strip() for c in df.columns]
                            col_sym = next((c for c in df.columns if "Symbol" in c), "Symbol")
                            col_amt = next((c for c in df.columns if "Amt" in c and "Fin" in c), None)
                            col_qty = next((c for c in df.columns if "Qty" in c and "Fin" in c), None)
                            
                            if col_amt:
                                for _, r in df.sort_values(by=col_amt, ascending=False).head(10).iterrows():
                                    data['top_val'].append((r[col_sym], r[col_amt]/100))
                            if col_qty:
                                for _, r in df.sort_values(by=col_qty, ascending=False).head(10).iterrows():
                                    data['top_vol'].append((r[col_sym], r[col_qty]))
                break # Found data, stop loop
            except:
                continue
        
        if not data: return jsonify({"error": "No MTF data found in last 3 days"}), 500

        # --- IMAGE GENERATION (Matplotlib) ---
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        FONT_MTF_BOLD = os.path.join(BASE_DIR, "fonts", "Roboto-Bold.ttf")
        
        def get_font():
            return fm.FontProperties(fname=FONT_MTF_BOLD) if os.path.exists(FONT_MTF_BOLD) else fm.FontProperties()

        COLORS = {'bg': '#111827', 'card_bg': '#1F2937', 'text': '#E5E7EB', 'accent': '#3B82F6', 'pos': '#10B981', 'neg': '#F43F5E'}
        
        fig = plt.figure(figsize=(16, 9), facecolor=COLORS['bg'])
        ax = fig.add_axes([0,0,1,1]); ax.axis('off')
        font_main = get_font()
        
        fig.text(0.05, 0.92, "MTF Market Insights", fontproperties=font_main, fontsize=36, color='#F9FAFB')
        fig.text(0.05, 0.88, f"Analysis | {data['date']}", fontproperties=font_main, fontsize=16, color='#9CA3AF')

        # KPI Cards
        kpis = [
            ("Added", f"₹{data['added']:,.0f} Cr", COLORS['pos']),
            ("Liquidated", f"₹{data['liquidated']:,.0f} Cr", COLORS['neg']),
            ("Net Flow", f"{'+' if data['net']>=0 else ''}₹{data['net']:,.0f} Cr", COLORS['pos'] if data['net']>=0 else COLORS['neg']),
            ("Total Book", f"₹{data['industry_book']:,.0f} Cr", COLORS['accent'])
        ]
        
        for i, (t, v, c) in enumerate(kpis):
            x = 0.05 + i*0.23
            ax.add_patch(patches.FancyBboxPatch((x, 0.68), 0.20, 0.15, boxstyle="round,pad=0.02", fc=COLORS['card_bg'], ec='none'))
            fig.text(x + 0.1, 0.79, t, ha='center', fontproperties=font_main, fontsize=14, color='#9CA3AF')
            fig.text(x + 0.1, 0.73, v, ha='center', fontproperties=font_main, fontsize=24, color=c)

        # Tables
        def draw_list(title, items, x_pos, is_vol):
            fig.text(x_pos, 0.60, title, fontproperties=font_main, fontsize=18, color=COLORS['accent'])
            y = 0.54
            for idx, (sym, val) in enumerate(items):
                ax.add_patch(patches.Rectangle((x_pos, y-0.01), 0.40, 0.045, fc=(COLORS['card_bg'] if idx%2==0 else COLORS['bg'])))
                val_str = f"{val/1e6:.1f}M" if is_vol and val>1e6 else (f"{val/1e3:.0f}K" if is_vol else f"₹{val:,.1f} Cr")
                col = COLORS['accent'] if is_vol else COLORS['pos']
                fig.text(x_pos+0.02, y+0.01, f"{idx+1}. {sym}", fontproperties=font_main, fontsize=15, color=COLORS['text'])
                fig.text(x_pos+0.38, y+0.01, val_str, fontproperties=font_main, fontsize=15, color=col, ha='right')
                y -= 0.05

        draw_list("Top 10 Additions (Value)", data.get('top_val', []), 0.05, False)
        draw_list("Top 10 Volume Buzzers", data.get('top_vol', []), 0.52, True)

        fig.text(0.98, 0.02, f"@ChartWizMani | {data['date']}", ha='right', fontproperties=font_main, fontsize=12, color='#9CA3AF')
        
        filename = "/tmp/mtf_insights.png"
        plt.savefig(filename, dpi=100, facecolor=COLORS['bg'])
        plt.close()

        # --- TWITTER POST ---
        api = get_twitter_api()
        if api:
            sign = "+" if data['net'] >= 0 else ""
            txt = (f"MTF Insights | {data['date']}\n\nAdded: ₹{data['added']:,.0f} Cr\nLiquidated: ₹{data['liquidated']:,.0f} Cr\n"
                   f"Net: {sign}₹{data['net']:,.0f} Cr\nTotal Book: ₹{data['industry_book']:,.0f} Cr\n\n#MTF #Nifty")
            media = api.media_upload(filename)
            api.update_status(status=txt, media_ids=[media.media_id])

        return jsonify({"status": "posted", "date": data['date']}), 200

    except Exception as e:
        print(f"MTF Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return "Tweet Bot Optimized Running!"
