    # -*- coding: utf-8 -*-
    # Author: ChartWizMani
    # Date: 19-Jul-2025
    # Description: Generates and posts financial market updates to Twitter. This version fixes the MTF data fetching error.

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
        """Loads the font file. Exits if the font is not found."""
        if not os.path.exists(FONT_PATH):
            print(f"FATAL: Font file not found at {FONT_PATH}. Exiting.")
            sys.exit(1)
        return ImageFont.truetype(FONT_PATH, size)

    def draw_text(draw, position, text, font, fill, anchor="mm"):
        """A helper function to draw text on the image."""
        draw.text(position, text, font=font, fill=fill, anchor=anchor)

    # --- Data Fetching ---
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
        """Fetches live data for a ticker. Returns None on failure."""
        try:
            hist = yf.Ticker(ticker_symbol).history(period="2d")
            if len(hist) < 2:
                print(f"ERROR: Not enough history for {ticker_symbol}.")
                return None, None
            change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            return f"{hist['Close'].iloc[-1]:,.2f}", f"{change:+.2f}%"
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
            # --- THIS IS THE FIX ---
            # Using a more realistic User-Agent to avoid being blocked.
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
            print("FATAL: Twitter API credentials not found in environment. Cannot post.")
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
            print(f"FATAL: Error posting to Twitter: {e}")

    # --- Main Execution ---
    def main():
        parser = argparse.ArgumentParser(description="Generate and post financial market updates.")
        parser.add_argument('job', choices=['global', 'mtf'], help="Specify job: 'global' or 'mtf'.")
        parser.add_argument('--post', action='store_true', help="Add this flag to actually post to Twitter.")
        args = parser.parse_args()

        if args.job == 'global':
            print("\n--- Running Global Market Update Job ---")
            data = fetch_global_market_data()
        else: # mtf
            print("\n--- Running MTF Insights Update Job ---")
            data = fetch_mtf_data()

        if data is None:
            print("\nFATAL: Could not fetch live data. Aborting process to prevent posting stale information.")
            sys.exit(1)

        if args.job == 'global':
            image_file = create_market_update_image(data)
        else: # mtf
            image_file = create_mtf_insights_image(data)
        
        tweet_text = build_tweet_text(data, args.job)
        
        text_filename = f"{args.job}_market_update.txt"
        with open(text_filename, 'w', encoding='utf-8') as f:
            f.write(tweet_text)
        print(f"✓ Image created: {image_file}")
        print(f"✓ Tweet content saved to {text_filename}")

        if args.post:
            post_to_twitter(tweet_text, image_file)
        else:
            print("\n✓ Job finished successfully (local test mode).")
            print("To post to Twitter, run the command again with the --post flag.")
        
        print(f"\n--- Job '{args.job}' finished. ---\n")

    if __name__ == '__main__':
        main()
    