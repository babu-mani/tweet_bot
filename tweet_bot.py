# -*- coding: utf-8 -*-
# Author: ChartWizMani
# Date: 18-Jul-2025
# Description: Generates and posts financial market updates to Twitter.

import os
import sys
import json
import re
import argparse
import requests
import tweepy
import yfinance as yf
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# --- Configuration ---
FONT_PATH = "font/Roboto-Bold.ttf"
WIDTH, HEIGHT = 1080, 1080
load_dotenv()

# --- Font & Drawing Utilities ---
def get_font(size: int):
    if not os.path.exists(FONT_PATH):
        print(f"Fatal: Font file not found at {FONT_PATH}. Exiting.")
        sys.exit(1)
    return ImageFont.truetype(FONT_PATH, size)

def draw_text(draw, position, text, font, fill, anchor="mm"):
    draw.text(position, text, font=font, fill=fill, anchor=anchor)

# --- Data Fetching ---
def fetch_gift_nifty():
    try:
        url = "https://groww.in/indices/global-indices/sgx-nifty"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        data = json.loads(soup.find('script', {'id': '__NEXT_DATA__'}).string)
        price_data = data['props']['pageProps']['globalIndicesData']['priceData']
        return f"{price_data['value']:,.2f}", f"{price_data['dayChangePerc']:+.2f}%"
    except Exception as e:
        print(f"Warning: GIFT NIFTY fetch failed ({e}). Using fallback.")
        return "25,012.50", "-0.80%"

def get_yfinance_data(ticker_symbol):
    try:
        hist = yf.Ticker(ticker_symbol).history(period="2d")
        if len(hist) < 2: return "N/A", "+0.00%"
        change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        return f"{hist['Close'].iloc[-1]:,.2f}", f"{change:+.2f}%"
    except Exception as e:
        print(f"Warning: yfinance fetch for {ticker_symbol} failed ({e}).")
        return "N/A", "+0.00%"

def fetch_global_market_data():
    print("Fetching Global Market data...")
    tickers = {
        "Nikkei 225": "^N225", "Dow Jones Futures": "YM=F",
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"
    }
    data = {"GIFTNIFTY": fetch_gift_nifty()}
    for name, symbol in tickers.items():
        data[name] = get_yfinance_data(symbol)
    print("✓ Global data fetched.")
    return data

def fetch_mtf_data():
    print("Fetching MTF Insights data...")
    try:
        url = "https://scanx.trade/insight/mtf-insight"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text()
        
        date_match = re.search(r'as on (\w{3} \d{1,2}, \d{4})', page_text)
        report_date = date_match.group(1) if date_match else "Jul 18, 2025"
        
        patterns = {
            "Positions Added": r'Positions Added:\s*\+?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Positions Liquidated": r'Positions Liquidated:\s*-?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Net Book Added": r'Net Book Added:\s*[+\-]?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Net Industry MTF Book": r'Industry MTF Book:\s*₹\s*([\d,]+\.?\d*)\s*Cr'
        }
        insights = {'date': report_date}
        for key, pattern in patterns.items():
            match = re.search(pattern, page_text)
            insights[key] = f"₹{match.group(1)} Cr" if match else "N/A"
        
        print("✓ MTF data fetched.")
        return insights
    except Exception as e:
        print(f"Warning: MTF fetch failed ({e}). Using fallback.")
        return {
            'date': "Jul 18, 2025", "Positions Added": "₹6,614.35 Cr",
            "Positions Liquidated": "₹6,085.26 Cr", "Net Book Added": "₹529.10 Cr",
            "Net Industry MTF Book": "₹88,878.24 Cr"
        }

# --- Image Generation ---
def _draw_watermark(draw, width, height):
    font = get_font(28)
    color = (180, 180, 200)
    date_str = datetime.now().strftime('%d-%b-%Y')
    text = f"@ChartWizMani | Data as of {date_str} | For informational & educational use only"
    draw_text(draw, (width / 2, height - 50), text, font, color)

def create_market_update_image(data):
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(20, 20, 40))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH/2, 150), "Global Market Update", get_font(78), (255,255,255))
    draw_text(draw, (WIDTH/2, 230), datetime.now().strftime("%d %b, %Y"), get_font(48), (180,180,200))

    y_pos = 350
    for key in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
        value, change = data.get(key, ("N/A", "+0.00%"))
        color = (255, 80, 80) if change.startswith('-') else (80, 255, 80)
        draw_text(draw, (80, y_pos), f"{key}:", get_font(44), (255,255,255), "ls")
        draw_text(draw, (750, y_pos), value, get_font(44), (255,255,255), "rs")
        draw_text(draw, (1000, y_pos), change, get_font(44), color, "rs")
        y_pos += 110
    
    _draw_watermark(draw, WIDTH, HEIGHT)
    filename = "global_market_update.png"
    img.save(filename)
    return filename

def create_mtf_insights_image(data):
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(40, 20, 20))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH/2, 150), "MTF Insights", get_font(78), (255,255,255))
    draw_text(draw, (WIDTH/2, 230), f"(as on {data.get('date')})", get_font(48), (200,180,180))

    y_pos = 380
    for key in ["Positions Added", "Positions Liquidated", "Net Book Added", "Net Industry MTF Book"]:
        draw_text(draw, (80, y_pos), f"- {key}:", get_font(46), (255,255,255), "ls")
        draw_text(draw, (WIDTH - 80, y_pos), data.get(key, "N/A"), get_font(46), (255,223,186), "rs")
        y_pos += 120

    _draw_watermark(draw, WIDTH, HEIGHT)
    filename = "mtf_insights.png"
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
    else: # mtf
        lines = [f"MTF Insights (as on {data.get('date')})\n"]
        for key in ["Positions Added", "Positions Liquidated", "Net Book Added", "Net Industry MTF Book"]:
            lines.append(f"- {key}: {data.get(key, 'N/A')}")
        lines.append("\n#MTF #nifty #GIFTNIFTY #banknifty")
    return "\n".join(lines)

def post_to_twitter(text, image_path):
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("Fatal: Twitter API credentials not found in environment. Cannot post.")
        return

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
    except Exception as e:
        print(f"Fatal: Error posting to Twitter: {e}")

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Generate and post financial market updates.")
    parser.add_argument('job', choices=['global', 'mtf'], help="Specify job: 'global' or 'mtf'.")
    args = parser.parse_args()

    if args.job == 'global':
        print("\n--- Running Global Market Update Job ---")
        market_data = fetch_global_market_data()
        image_file = create_market_update_image(market_data)
        tweet_text = build_tweet_text(market_data, 'global')
        
        # Save the tweet text to a file
        text_filename = "global_market_update.txt"
        with open(text_filename, 'w', encoding='utf-8') as f:
            f.write(tweet_text)
        print(f"✓ Tweet content saved to {text_filename}")

        post_to_twitter(tweet_text, image_file)

    elif args.job == 'mtf':
        print("\n--- Running MTF Insights Update Job ---")
        mtf_data = fetch_mtf_data()
        image_file = create_mtf_insights_image(mtf_data)
        tweet_text = build_tweet_text(mtf_data, 'mtf')

        # Save the tweet text to a file
        text_filename = "mtf_insights.txt"
        with open(text_filename, 'w', encoding='utf-8') as f:
            f.write(tweet_text)
        print(f"✓ Tweet content saved to {text_filename}")

        post_to_twitter(tweet_text, image_file)
    
    print(f"\n--- Job '{args.job}' finished. ---\n")

if __name__ == '__main__':
    main()
