# api/index.py

from flask import Flask, jsonify, request
import os
import json
import re
import requests
import tweepy
import yfinance as yf
from datetime import datetime
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# --- Configuration ---
# FONT_PATH is set assuming Roboto-Bold.ttf is in the same 'api' directory
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Roboto-Bold.ttf")
WIDTH, HEIGHT = 1080, 1080


# --- Font & Drawing Utilities ---
def get_font(size: int):
    """Loads the font file. Raises FileNotFoundError if the font is not found."""
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(
            f"Font file not found at {FONT_PATH}. Please ensure it's deployed."
        )
    return ImageFont.truetype(FONT_PATH, size)


def draw_text(draw, position, text, font, fill, anchor="mm"):
    """A helper to draw text on the image."""
    draw.text(position, text, font=font, fill=fill, anchor=anchor)


# --- Data Fetching (with Safe-Fail Logic) ---
def fetch_gift_nifty():
    """Fetches live GIFT NIFTY data. Returns (value, change) or (None, None)."""
    try:
        url = "https://groww.in/indices/global-indices/sgx-nifty"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        data = json.loads(soup.find("script", {"id": "__NEXT_DATA__"}).string)
        price = data["props"]["pageProps"]["globalIndicesData"]["priceData"]
        return f"{price['value']:,.2f}", f"{price['dayChangePerc']:+.2f}%"
    except Exception:
        return None, None


def get_yfinance_data(symbol: str):
    """Fetches last two days of close prices via yfinance."""
    try:
        hist = yf.Ticker(symbol).history(period="2d")
        if len(hist) < 2:
            return None, None
        prev, last = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
        change = (last - prev) / prev * 100
        return f"{last:,.2f}", f"{change:+.2f}%"
    except Exception:
        return None, None


def fetch_global_market_data():
    """Fetches global market data. Returns dict or None."""
    data = {}
    # GIFT NIFTY
    gn_val, gn_chg = fetch_gift_nifty()
    if not gn_val:
        return None
    data["GIFTNIFTY"] = (gn_val, gn_chg)

    # Other indices
    tickers = {
        "Nikkei 225": "^N225",
        "Dow Jones Futures": "YM=F",
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Hang Seng": "^HSI",
    }
    for name, sym in tickers.items():
        val, chg = get_yfinance_data(sym)
        if not val:
            return None
        data[name] = (val, chg)

    return data


def fetch_mtf_data():
    """Fetches MTF Insights. Returns dict or None."""
    try:
        url = "https://scanx.trade/insight/mtf-insight"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = BeautifulSoup(resp.text, "html.parser").get_text()

        # Extract report date
        date_match = re.search(r"as on (\w{3} \d{1,2}, \d{4})", text)
        report_date = date_match.group(1) if date_match else "Unknown Date"

        patterns = {
            "Positions Added": r"Positions Added:\s*\+?₹\s*([\d,]+\.?\d*)\s*Cr",
            "Positions Liquidated": r"Positions Liquidated:\s*-?₹\s*([\d,]+\.?\d*)\s*Cr",
            "Net Book Added": r"Net Book Added:\s*[+\-]?₹\s*([\d,]+\.?\d*)\s*Cr",
            "Net Industry MTF Book": r"Industry MTF Book:\s*₹\s*([\d,]+\.?\d*)\s*Cr",
        }

        insights = {"date": report_date}
        for key, pat in patterns.items():
            m = re.search(pat, text)
            if not m:
                return None
            insights[key] = f"₹{m.group(1)} Cr"

        return insights

    except Exception:
        return None


# --- Image Generation ---
def _draw_watermark(draw, width, height):
    try:
        font = get_font(28)
    except FileNotFoundError:
        return
    date_str = datetime.now().strftime("%d-%b-%Y")
    msg = f"@ChartWizMani | Data as of {date_str} | For informational use"
    draw_text(draw, (width / 2, height - 50), msg, font, (180, 180, 200))


def create_market_update_image(data: dict) -> str:
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(20, 20, 40))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH / 2, 150), "Global Market Update", get_font(78), (255, 255, 255))
    draw_text(draw, (WIDTH / 2, 230), datetime.now().strftime("%d %b, %Y"), get_font(48), (180, 180, 200))

    y = 360
    df = get_font(42)
    for key in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
        val, chg = data.get(key, ("N/A", "+0.00%"))
        col = (80, 255, 80) if not chg.startswith("-") else (255, 80, 80)
        draw_text(draw, (100, y), f"{key}:", df, (255, 255, 255), "ls")
        draw_text(draw, (750, y), val, df, (255, 255, 255), "rs")
        draw_text(draw, (WIDTH - 100, y), chg, df, col, "rs")
        y += 100

    _draw_watermark(draw, WIDTH, HEIGHT)
    path = "/tmp/global_market_update.png"
    img.save(path)
    return path


def create_mtf_insights_image(data: dict) -> str:
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(40, 20, 20))
    draw = ImageDraw.Draw(img)
    draw_text(draw, (WIDTH / 2, 150), "MTF Insights", get_font(78), (255, 255, 255))
    draw_text(draw, (WIDTH / 2, 230), f"(as on {data.get('date')})", get_font(48), (200, 180, 200))

    y = 380
    for key in [
        "Positions Added",
        "Positions Liquidated",
        "Net Book Added",
        "Net Industry MTF Book",
    ]:
        draw_text(draw, (80, y), f"- {key}:", get_font(46), (255, 255, 255), "ls")
        draw_text(draw, (WIDTH - 80, y), data.get(key, "N/A"), get_font(46), (255, 223, 186), "rs")
        y += 120

    _draw_watermark(draw, WIDTH, HEIGHT)
    path = "/tmp/mtf_insights.png"
    img.save(path)
    return path


# --- Tweet Text & Posting ---
def build_tweet_text(data: dict, job: str) -> str:
    if job == "global":
        lines = [f"Global Market Update – {datetime.now():%d %b, %Y}\n"]
        for k in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
            v, c = data.get(k, ("N/A", "+0.00%"))
            lines.append(f"{k}: {v} ({c})")
        lines.append("\n#GIFTNIFTY #Nifty #DowJones #Nasdaq #Nikkei #HangSeng")
    else:
        lines = [f"MTF Insights (as on {data.get('date')})\n"]
        for k in [
            "Positions Added",
            "Positions Liquidated",
            "Net Book Added",
            "Net Industry MTF Book",
        ]:
            lines.append(f"- {k}: {data.get(k, 'N/A')}")
        lines.append("\n#MTF #nifty #GIFTNIFTY #banknifty")
    return "\n".join(lines)


def post_to_twitter(text: str, img_path: str) -> None:
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        raise EnvironmentError("Twitter API credentials missing.")

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api_v1 = tweepy.API(auth)

    media = api_v1.media_upload(filename=img_path)
    client.create_tweet(text=text, media_ids=[media.media_id_string])


# --- Flask Routes ---
@app.route("/global-market-update", methods=["GET"])
def global_market_update():
    data = fetch_global_market_data()
    if not data:
        return jsonify({"status": "error", "message": "Could not fetch global market data."}), 500

    img = create_market_update_image(data)
    tweet = build_tweet_text(data, "global")
    post_to_twitter(tweet, img)
    os.remove(img)
    return jsonify({"status": "success", "message": "Global market update posted."}), 200


@app.route("/mtf-insights-update", methods=["GET"])
def mtf_insights_update():
    data = fetch_mtf_data()
    if not data:
        return jsonify({"status": "error", "message": "Could not fetch MTF insights data."}), 500

    img = create_mtf_insights_image(data)
    tweet = build_tweet_text(data, "mtf")
    post_to_twitter(tweet, img)
    os.remove(img)
    return jsonify({"status": "success", "message": "MTF insights update posted."}), 200


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Tweet Bot API running!"}), 200


# Expose Flask app to Vercel
handler = app
