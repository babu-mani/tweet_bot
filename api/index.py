# -*- coding: utf-8 -*-
# Author: ChartWizMani
# Date: 03-Dec-2025 (Updated for Robust Data Fetching)
# Description: Generates and posts financial market updates to Twitter.

from flask import Flask, jsonify, request
import os
import sys
import json
import re
import requests
import tweepy
import yfinance as yf
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# --- FIX 1: Set yfinance cache to a writable folder to stop "Read-only" errors ---
yf.set_tz_cache_location("/tmp/yf_tz_cache")

app = Flask(__name__)

# --- Configuration ---
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Roboto-Bold.ttf")

WIDTH, HEIGHT = 1080, 1080
load_dotenv() 

# --- Font & Drawing Utilities ---
def get_font(size: int):
    if not os.path.exists(FONT_PATH):
        print(f"FATAL: Font file not found at {FONT_PATH}.")
        raise FileNotFoundError(f"Font file not found at {FONT_PATH}.")
    return ImageFont.truetype(FONT_PATH, size)

def draw_text(draw, position, text, font, fill, anchor="mm"):
    draw.text(position, text, font=font, fill=fill, anchor=anchor)

# --- Data Fetching (with Safe-Fail Logic) ---
def fetch_gift_nifty():
    try:
        print("Fetching GIFT NIFTY data...")
        url = "https://groww.in/indices/global-indices/sgx-nifty"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        data = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).string)
        price_data = data['props']['pageProps']['globalIndicesData']['priceData']
        return f"{price_data['value']:,.2f}", f"{price_data['dayChangePerc']:+.2f}%"
    except Exception as e:
        print(f"ERROR: GIFT NIFTY fetch failed ({e}).")
        return None, None

def get_yfinance_data(ticker_symbol):
    """
    FIX 2: Improved logic. Fetches 1 month of data and picks the last 2 valid points.
    This handles weekends, holidays, and API gaps automatically.
    """
    try:
        # Fetch 1 month. This ensures we have data even if there are holidays/gaps.
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1mo")

        # Drop any empty rows (days where API returned null)
        hist = hist.dropna()

        # Check if we have at least 2 data points total in the last month
        if len(hist) < 2:
            print(f"ERROR: Failed to get at least 2 historical data points for {ticker_symbol}.")
            return None, None

        # .iloc[-1] is the LATEST available price (Today)
        # .iloc[-2] is the PREVIOUS available price (Yesterday or last trading day)
        current_close = hist['Close'].iloc[-1]
        previous_close = hist['Close'].iloc[-2]

        change = ((current_close - previous_close) / previous_close) * 100
        return f"{current_close:,.2f}", f"{change:+.2f}%"

    except Exception as e:
        print(f"ERROR: yfinance fetch for {ticker_symbol} failed ({e}).")
        return None, None

def fetch_global_market_data():
    """Fetches all global market data. Skips failed tickers instead of crashing."""
    print("Fetching Global Market data...")
    data = {}
    
    # NOTE: I recommend swapping YM=F for ^DJI if problems persist, 
    # but the new logic below should handle YM=F better now.
    tickers = {
        "Nikkei 225": "^N225", "Dow Jones Futures": "YM=F",
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"
    }
    
    gn_val, gn_chg = fetch_gift_nifty()
    # If GIFT Nifty fails, we can still post the others, or choose to fail. 
    # Current logic: continue even if GIFT Nifty fails (optional).
    if gn_val:
        data["GIFTNIFTY"] = (gn_val, gn_chg)
        print("✓ GIFTNIFTY data fetched.")
    else:
        print("⚠️ GIFTNIFTY failed, skipping.")

    for name, symbol in tickers.items():
        val, chg = get_yfinance_data(symbol)
        
        # FIX 3: If one ticker fails, SKIP it. Do not return None.
        if val is None: 
            print(f"⚠️ Skipping {name} ({symbol}) due to fetch failure.")
            continue 
            
        data[name] = (val, chg)
        print(f"✓ {name} data fetched.")
        
    print("✓ Global data fetch process completed.")
    return data

def fetch_mtf_data():
    """Fetches MTF Insights data. Returns None on failure."""
    print("Fetching MTF Insights data...")
    try:
        url = "https://scanx.trade/insight/mtf-insight"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text()

        date_match = re.search(r'as on (\w{3} \d{1,2}, \d{4})', page_text)
        report_date = date_match.group(1) if date_match else "Date not found"

        insights = {'date': report_date}

        fixed_patterns = {
            "Positions Added": r'Positions Added:\s*\+?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Positions Liquidated": r'Positions Liquidated:\s*(?P<sign>[+\-]?)\s*₹\s*(?P<value>[\d,]+\.?\d*)\s*Cr',
            "Industry MTF Book": r'Industry MTF Book:\s*₹\s*([\d,]+\.?\d*)\s*Cr'
        }

        net_book_pattern = r'(Net Book (?:Added|Liquidated)):\s*(?P<sign>[+\-]?)\s*₹\s*(?P<value>[\d,]+\.?\d*)\s*Cr'
        net_book_match = re.search(net_book_pattern, page_text)

        if net_book_match:
            net_book_label = net_book_match.group(1)
            captured_value_with_sign = f"{net_book_match.group('sign')}{net_book_match.group('value')}"
            insights[net_book_label] = f"₹{captured_value_with_sign} Cr"
            print(f"✓ '{net_book_label}' data fetched dynamically.")
        else:
            start_idx = page_text.find('Net Book')
            end_idx = page_text.find('Cr', start_idx)
            context = page_text[start_idx:end_idx+30] if start_idx != -1 and end_idx != -1 else "N/A"
            print(f"ERROR: Could not find dynamic 'Net Book' data. Page text around issue: {context}")
            return None 

        for key, pattern in fixed_patterns.items():
            match = re.search(pattern, page_text)
            if not match:
                print(f"ERROR: Could not find MTF data for '{key}'.")
                return None
            
            if key == "Positions Liquidated" and 'sign' in match.groupdict():
                captured_value_with_sign = f"{match.group('sign')}{match.group('value')}"
                insights[key] = f"₹{captured_value_with_sign} Cr"
            else:
                insights[key] = f"₹{match.group(1)} Cr"
            print(f"✓ '{key}' data fetched.")

        print("✓ MTF data fetched.")
        return insights 

    except Exception as e:
        print(f"ERROR: MTF fetch failed ({e}).")
        return None

# --- Image Generation ---
def _draw_watermark(draw, width, height):
    try:
        font = get_font(28)
    except FileNotFoundError as e:
        print(f"Warning: Watermark font not found. Skipping watermark. Error: {e}")
        return 

    color = (180, 180, 200)
    date_str = datetime.now().strftime('%d-%b-%Y')
    text = f"@ChartWizMani | Data as of {date_str} | For informational & educational use only"
    draw_text(draw, (width / 2, height - 50), text, font, color)

def create_market_update_image(data):
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(20, 20, 40))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH/2, 150), "Global Market Update", get_font(78), (255,255,255))
    draw_text(draw, (WIDTH/2, 230), datetime.now().strftime("%d %b, %Y"), get_font(48), (180,180,200))

    y_pos = 360
    data_font = get_font(42)
    # Even if data is missing for a key, .get() will return "N/A" so it won't crash
    for key in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
        value, change = data.get(key, ("N/A", "+0.00%"))
        color = (255, 80, 80) if change.startswith('-') else (80, 255, 80)
        draw_text(draw, (100, y_pos), f"{key}:", data_font, (255,255,255), "ls")
        draw_text(draw, (750, y_pos), value, data_font, (255,255,255), "rs")
        draw_text(draw, (WIDTH - 100, y_pos), change, data_font, color, "rs")
        y_pos += 100

    _draw_watermark(draw, WIDTH, HEIGHT)
    filename = "/tmp/global_market_update.png" 
    img.save(filename)
    return filename

def create_mtf_insights_image(data):
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(40, 20, 20))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH/2, 150), "MTF Insights", get_font(78), (255,255,255))
    draw_text(draw, (WIDTH/2, 230), f"(as on {data.get('date')})", get_font(48), (200,180,200))

    y_pos = 380
    ordered_keys_image = [
        "Positions Added",
        "Positions Liquidated",
        "Industry MTF Book"
    ]

    net_book_dynamic_key_image = None
    for k in data.keys():
        if k.startswith("Net Book"):
            net_book_dynamic_key_image = k
            break
    
    if net_book_dynamic_key_image:
        ordered_keys_image.insert(2, net_book_dynamic_key_image)

    for key in ordered_keys_image:
        draw_text(draw, (80, y_pos), f"- {key}:", get_font(46), (255,255,255), "ls")
        draw_text(draw, (WIDTH - 80, y_pos), data.get(key, "N/A"), get_font(46), (255,223,186), "rs")
        y_pos += 120

    _draw_watermark(draw, WIDTH, HEIGHT)
    filename = "/tmp/mtf_insights.png" 
    img.save(filename)
    return filename

# --- Text & Twitter ---
def build_tweet_text(data, job_type):
    if job_type == 'global':
        lines = [f"Global Market Update – {datetime.now().strftime('%d %b, %Y')}\n"]
        for key in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
            value, change = data.get(key, ("N/A", "+0.00%"))
            lines.append(f"{key}: {value} ({change})")
        lines.append("\n#GIFTNIFTY #Nifty #DowJones #Nasdaq #Nikkei #HangSeng")
    else: 
        lines = [f"MTF Insights (as on {data.get('date')})\n"]
        
        ordered_keys = [
            "Positions Added",
            "Positions Liquidated",
            "Industry MTF Book"
        ]

        net_book_dynamic_key = None
        for k in data.keys():
            if k.startswith("Net Book"):
                net_book_dynamic_key = k
                break
        
        if net_book_dynamic_key:
            ordered_keys.insert(2, net_book_dynamic_key)

        for key in ordered_keys:
            lines.append(f"- {key}: {data.get(key, 'N/A')}")
        lines.append("\n#MTF #nifty #GIFTNIFTY #banknifty")
    return "\n".join(lines)

def post_to_twitter(text, image_path):
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("FATAL: Twitter API credentials not found in environment. Cannot post.")
        raise ValueError("Twitter API credentials missing.")

    try:
        print("Authenticating with Twitter...")
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_token_secret
        )
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api_v1 = tweepy.API(auth)

        print(f"Uploading media: {image_path}...")
        media = api_v1.media_upload(filename=image_path)

        print("Posting tweet...")
        client.create_tweet(text=text, media_ids=[media.media_id_string])
        print("✓ Tweet posted successfully!")
        return True
    except Exception as e:
        print(f"FATAL: Error posting to Twitter: {e}")
        raise 

@app.route('/global-market-update', methods=['GET'])
def global_market_update():
    try:
        print("Received request for Global Market Update.")
        
        # We allow data to be partial now. It returns a dict even if some keys are missing.
        data = fetch_global_market_data()

        # Only crash if data is totally empty (meaning everything failed)
        if not data:
            print("Failed to fetch global market data.")
            return jsonify({"status": "error", "message": "Could not fetch any global market data."}), 500

        image_file = create_market_update_image(data)
        tweet_text = build_tweet_text(data, 'global')

        post_to_twitter(tweet_text, image_file)

        if os.path.exists(image_file):
            os.remove(image_file)

        return jsonify({"status": "success", "message": "Global market update posted."}), 200

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/mtf-insights-update', methods=['GET'])
def mtf_insights_update():
    try:
        print("Received request for MTF Insights Update.")
        data = fetch_mtf_data()

        if data is None:
            print("Failed to fetch MTF insights data.")
            return jsonify({"status": "error", "message": "Could not fetch live MTF insights data."}), 500

        image_file = create_mtf_insights_image(data)
        tweet_text = build_tweet_text(data, 'mtf')

        post_to_twitter(tweet_text, image_file)

        if os.path.exists(image_file):
            os.remove(image_file)

        return jsonify({"status": "success", "message": "MTF insights update posted."}), 200

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "ok", "message": "Tweet Bot API is running!"}), 200
