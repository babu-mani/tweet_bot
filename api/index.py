# api/index.py
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

app = Flask(__name__)

# --- Configuration ---
# FONT_PATH is now set assuming Roboto-Bold.ttf is directly in the 'api' directory
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Roboto-Bold.ttf")

WIDTH, HEIGHT = 1080, 1080
load_dotenv() # Load environment variables from .env file

# --- Font & Drawing Utilities ---
def get_font(size: int):
    """Loads the font file. Raises FileNotFoundError if the font is not found."""
    if not os.path.exists(FONT_PATH):
        print(f"FATAL: Font file not found at {FONT_PATH}.")
        raise FileNotFoundError(f"Font file not found at {FONT_PATH}. Please ensure it's deployed.")
    return ImageFont.truetype(FONT_PATH, size)

def draw_text(draw, position, text, font, fill, anchor="mm"):
    """A helper function to draw text on the image."""
    draw.text(position, text, font=font, fill=fill, anchor=anchor)

# --- Data Fetching (with Safe-Fail Logic) ---
def fetch_gift_nifty():
    """Fetches live GIFT NIFTY data. Returns None on failure."""
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
    Fetches live data for a ticker. Tries longer periods if 2d fails to ensure
    at least two distinct historical close prices are obtained for change calculation.
    Returns (current_close, change_percent) or (None, None) on failure.
    """
    try:
        # Try with "2d" first (standard case)
        hist = yf.Ticker(ticker_symbol).history(period="2d")

        # If not enough history, try a longer period to find two distinct days
        if len(hist) < 2:
            print(f"WARNING: Not enough history for {ticker_symbol} with '2d' period. Trying '5d'...")
            hist = yf.Ticker(ticker_symbol).history(period="5d") # Try 5 days

            if len(hist) < 2:
                print(f"WARNING: Still not enough history for {ticker_symbol} with '5d' period. Trying '1wk'...")
                hist = yf.Ticker(ticker_symbol).history(period="1wk") # Try 1 week

        # After trying different periods, check if we finally have at least 2 rows
        if len(hist) < 2:
            print(f"ERROR: Failed to get at least 2 historical data points for {ticker_symbol} even after trying longer periods.")
            return None, None

        # Get the most recent close
        current_close = hist['Close'].iloc[-1]
        
        # Get the previous close. If the last two points are from the same day (e.g., due to a late run),
        # this might not be strictly 'previous day'. But for daily periods, it's usually fine.
        previous_close = hist['Close'].iloc[-2]

        change = ((current_close - previous_close) / previous_close) * 100
        return f"{current_close:,.2f}", f"{change:+.2f}%"

    except Exception as e:
        print(f"ERROR: yfinance fetch for {ticker_symbol} failed ({e}).")
        return None, None

def fetch_global_market_data():
    """Fetches all global market data. Returns None if any part fails."""
    print("Fetching Global Market data...")
    data = {}
    tickers = {
        "Nikkei 225": "^N225", "Dow Jones Futures": "YM=F",
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Hang Seng": "^HSI"
    }
    gn_val, gn_chg = fetch_gift_nifty()
    if gn_val is None: return None
    data["GIFTNIFTY"] = (gn_val, gn_chg)
    print("✓ GIFTNIFTY data fetched.")
    for name, symbol in tickers.items():
        val, chg = get_yfinance_data(symbol)
        if val is None: return None
        data[name] = (val, chg)
        print(f"✓ {name} data fetched.")
    print("✓ All global data fetched.")
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

        patterns = {
            "Positions Added": r'Positions Added:\s*\+?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Positions Liquidated": r'Positions Liquidated:\s*-?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Net Book Added": r'Net Book Added:\s*[+\-]?₹\s*([\d,]+\.?\d*)\s*Cr',
            "Net Industry MTF Book": r'Industry MTF Book:\s*₹\s*([\d,]+\.?\d*)\s*Cr'
        }
        insights = {'date': report_date}
        for key, pattern in patterns.items():
            match = re.search(pattern, page_text)
            if not match:
                print(f"ERROR: Could not find MTF data for '{key}'.")
                return None
            insights[key] = f"₹{match.group(1)} Cr"

        print("✓ MTF data fetched.")
        return insights
    except Exception as e:
        print(f"ERROR: MTF fetch failed ({e}).")
        return None

# --- Image Generation ---
def _draw_watermark(draw, width, height):
    # Ensure FONT_PATH is correctly set for the environment
    try:
        font = get_font(28)
    except FileNotFoundError as e:
        print(f"Warning: Watermark font not found. Skipping watermark. Error: {e}")
        return # Skip drawing watermark if font is missing

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
    for key in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
        value, change = data.get(key, ("N/A", "+0.00%"))
        color = (255, 80, 80) if change.startswith('-') else (80, 255, 80)
        draw_text(draw, (100, y_pos), f"{key}:", data_font, (255,255,255), "ls")
        draw_text(draw, (750, y_pos), value, data_font, (255,255,255), "rs")
        draw_text(draw, (WIDTH - 100, y_pos), change, data_font, color, "rs")
        y_pos += 100

    _draw_watermark(draw, WIDTH, HEIGHT)
    filename = "/tmp/global_market_update.png" # Use /tmp for serverless functions
    img.save(filename)
    return filename

def create_mtf_insights_image(data):
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(40, 20, 20))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH/2, 150), "MTF Insights", get_font(78), (255,255,255))
    draw_text(draw, (WIDTH/2, 230), f"(as on {data.get('date')})", get_font(48), (200,180,200))

    y_pos = 380
    for key in ["Positions Added", "Positions Liquidated", "Net Book Added", "Net Industry MTF Book"]:
        draw_text(draw, (80, y_pos), f"- {key}:", get_font(46), (255,255,255), "ls")
        draw_text(draw, (WIDTH - 80, y_pos), data.get(key, "N/A"), get_font(46), (255,223,186), "rs")
        y_pos += 120

    _draw_watermark(draw, WIDTH, HEIGHT)
    filename = "/tmp/mtf_insights.png" # Use /tmp for serverless functions
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
        raise # Re-raise the exception to be caught by the Flask app


@app.route('/global-market-update', methods=['GET'])
def global_market_update():
    """
    Endpoint to trigger the global market update.
    This will fetch data, create an image, and post to Twitter.
    """
    try:
        print("Received request for Global Market Update.")
        data = fetch_global_market_data()

        if data is None:
            print("Failed to fetch global market data.")
            return jsonify({"status": "error", "message": "Could not fetch live global market data."}), 500

        image_file = create_market_update_image(data)
        tweet_text = build_tweet_text(data, 'global')

        # Post to Twitter
        post_to_twitter(tweet_text, image_file)

        # Clean up the temporary image file
        if os.path.exists(image_file):
            os.remove(image_file)

        return jsonify({"status": "success", "message": "Global market update posted."}), 200

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except ValueError as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/mtf-insights-update', methods=['GET'])
def mtf_insights_update():
    """
    Endpoint to trigger the MTF insights update.
    This will fetch data, create an image, and post to Twitter.
    """
    try:
        print("Received request for MTF Insights Update.")
        data = fetch_mtf_data()

        if data is None:
            print("Failed to fetch MTF insights data.")
            return jsonify({"status": "error", "message": "Could not fetch live MTF insights data."}), 500

        image_file = create_mtf_insights_image(data)
        tweet_text = build_tweet_text(data, 'mtf')

        # Post to Twitter
        post_to_twitter(tweet_text, image_file)

        # Clean up the temporary image file
        if os.path.exists(image_file):
            os.remove(image_file)

        return jsonify({"status": "success", "message": "MTF insights update posted."}), 200

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except ValueError as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500

# Optional: A root endpoint for health check
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "ok", "message": "Tweet Bot API is running!"}), 200
