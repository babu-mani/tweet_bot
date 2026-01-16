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

# --- FIX 1: Writable yfinance cache ---
yf.set_tz_cache_location("/tmp/yf_tz_cache")

app = Flask(__name__)

# --- Configuration ---
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Roboto-Bold.ttf")
WIDTH, HEIGHT = 1080, 1080
load_dotenv()

# --- Font Helpers ---
def get_font(size: int):
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Font not found: {FONT_PATH}")
    return ImageFont.truetype(FONT_PATH, size)

def draw_text(draw, position, text, font, fill, anchor="mm"):
    draw.text(position, text, font=font, fill=fill, anchor=anchor)

# --- Data Fetching ---
def fetch_gift_nifty():
    try:
        url = "https://groww.in/indices/global-indices/sgx-nifty"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        data = json.loads(soup.find("script", {"id": "__NEXT_DATA__"}).string)
        p = data["props"]["pageProps"]["globalIndicesData"]["priceData"]
        return f"{p['value']:,.2f}", f"{p['dayChangePerc']:+.2f}%"
    except Exception:
        return None, None

def get_yfinance_data(symbol):
    try:
        hist = yf.Ticker(symbol).history(period="1mo").dropna()
        if len(hist) < 2:
            return None, None
        curr = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        chg = ((curr - prev) / prev) * 100
        return f"{curr:,.2f}", f"{chg:+.2f}%"
    except Exception:
        return None, None

def fetch_global_market_data():
    data = {}
    tickers = {
        "Nikkei 225": "^N225",
        "Dow Jones Futures": "YM=F",
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "Hang Seng": "^HSI",
    }

    gn_val, gn_chg = fetch_gift_nifty()
    if gn_val:
        data["GIFTNIFTY"] = (gn_val, gn_chg)

    for name, sym in tickers.items():
        v, c = get_yfinance_data(sym)
        if v:
            data[name] = (v, c)

    return data

def fetch_mtf_data():
    try:
        url = "https://scanx.trade/insight/mtf-insight"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        txt = soup.get_text()

        insights = {}
        d = re.search(r"as on (\w{3} \d{1,2}, \d{4})", txt)
        insights["date"] = d.group(1) if d else "N/A"

        patterns = {
            "Positions Added": r"Positions Added:\s*\+?₹\s*([\d,]+\.?\d*)\s*Cr",
            "Positions Liquidated": r"Positions Liquidated:\s*([+\-]?)₹\s*([\d,]+\.?\d*)\s*Cr",
            "Industry MTF Book": r"Industry MTF Book:\s*₹\s*([\d,]+\.?\d*)\s*Cr",
        }

        net = re.search(r"(Net Book (?:Added|Liquidated)):\s*([+\-]?)₹\s*([\d,]+\.?\d*)\s*Cr", txt)
        if net:
            insights[net.group(1)] = f"₹{net.group(2)}{net.group(3)} Cr"

        for k, p in patterns.items():
            m = re.search(p, txt)
            if not m:
                return None
            if k == "Positions Liquidated":
                insights[k] = f"₹{m.group(1)}{m.group(2)} Cr"
            else:
                insights[k] = f"₹{m.group(1)} Cr"

        return insights
    except Exception:
        return None

# --- Image Creation ---
def watermark(draw):
    txt = f"@ChartWizMani | {datetime.now().strftime('%d-%b-%Y')} | For education only"
    draw_text(draw, (WIDTH / 2, HEIGHT - 50), txt, get_font(26), (180, 180, 200))

def create_market_image(data):
    img = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 40))
    d = ImageDraw.Draw(img)

    draw_text(d, (WIDTH / 2, 150), "Global Market Update", get_font(78), (255, 255, 255))
    draw_text(d, (WIDTH / 2, 230), datetime.now().strftime("%d %b, %Y"), get_font(48), (180, 180, 200))

    y = 360
    for k in ["GIFTNIFTY", "Nikkei 225", "Dow Jones Futures", "S&P 500", "Nasdaq", "Hang Seng"]:
        v, c = data.get(k, ("N/A", "+0.00%"))
        col = (255, 80, 80) if c.startswith("-") else (80, 255, 80)
        draw_text(d, (100, y), f"{k}:", get_font(42), (255, 255, 255), "ls")
        draw_text(d, (750, y), v, get_font(42), (255, 255, 255), "rs")
        draw_text(d, (WIDTH - 100, y), c, get_font(42), col, "rs")
        y += 100

    watermark(d)
    path = "/tmp/global_market.png"
    img.save(path)
    return path

def create_mtf_image(data):
    img = Image.new("RGB", (WIDTH, HEIGHT), (40, 20, 20))
    d = ImageDraw.Draw(img)

    draw_text(d, (WIDTH / 2, 150), "MTF Insights", get_font(78), (255, 255, 255))
    draw_text(d, (WIDTH / 2, 230), f"(as on {data.get('date')})", get_font(48), (200, 180, 200))

    y = 380
    for k, v in data.items():
        if k == "date":
            continue
        draw_text(d, (80, y), f"- {k}:", get_font(46), (255, 255, 255), "ls")
        draw_text(d, (WIDTH - 80, y), v, get_font(46), (255, 223, 186), "rs")
        y += 120

    watermark(d)
    path = "/tmp/mtf.png"
    img.save(path)
    return path

# --- Tweet ---
def build_tweet(data, t):
    if t == "global":
        lines = [f"Global Market Update – {datetime.now().strftime('%d %b, %Y')}\n"]
        for k, (v, c) in data.items():
            lines.append(f"{k}: {v} ({c})")
        lines.append("\n#GIFTNIFTY #Nifty #DowJones #Nasdaq")
    else:
        lines = [f"MTF Insights (as on {data.get('date')})\n"]
        for k, v in data.items():
            if k != "date":
                lines.append(f"- {k}: {v}")
        lines.append("\n#MTF #Nifty #BankNifty")
    return "\n".join(lines)

def post_to_twitter(text, image):
    client = tweepy.Client(
        consumer_key=os.getenv("TWITTER_API_KEY"),
        consumer_secret=os.getenv("TWITTER_API_SECRET"),
        access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
        access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    )

    auth = tweepy.OAuth1UserHandler(
        os.getenv("TWITTER_API_KEY"),
        os.getenv("TWITTER_API_SECRET"),
        os.getenv("TWITTER_ACCESS_TOKEN"),
        os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    )

    api = tweepy.API(auth)
    media = api.media_upload(image)
    client.create_tweet(text=text, media_ids=[media.media_id_string])

# --- Routes ---
@app.route("/global-market-update")
def global_update():
    data = fetch_global_market_data()
    if not data:
        return jsonify({"status": "error"}), 500
    img = create_market_image(data)
    post_to_twitter(build_tweet(data, "global"), img)
    return jsonify({"status": "success"})

@app.route("/mtf-insights-update")
def mtf_update():
    data = fetch_mtf_data()
    if not data:
        return jsonify({"status": "error"}), 500
    img = create_mtf_image(data)
    post_to_twitter(build_tweet(data, "mtf"), img)
    return jsonify({"status": "success"})

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "ChartWizMani Tweet Bot running"})
