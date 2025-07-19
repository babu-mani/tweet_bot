# api/index.py
from flask import Flask, jsonify, request
import os
import sys
# Import the functions from your modified script
# Assuming tweet_bot_logic.py is in the same 'api' directory.
from . import tweet_bot_logic

app = Flask(__name__)

@app.route('/global-market-update', methods=['GET'])
def global_market_update():
    """
    Endpoint to trigger the global market update.
    This will fetch data, create an image, and post to Twitter.
    """
    try:
        print("Received request for Global Market Update.")
        data = tweet_bot_logic.fetch_global_market_data()

        if data is None:
            print("Failed to fetch global market data.")
            return jsonify({"status": "error", "message": "Could not fetch live global market data."}), 500

        image_file = tweet_bot_logic.create_market_update_image(data)
        tweet_text = tweet_bot_logic.build_tweet_text(data, 'global')

        # Post to Twitter
        tweet_bot_logic.post_to_twitter(tweet_text, image_file)

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
        data = tweet_bot_logic.fetch_mtf_data()

        if data is None:
            print("Failed to fetch MTF insights data.")
            return jsonify({"status": "error", "message": "Could not fetch live MTF insights data."}), 500

        image_file = tweet_bot_logic.create_mtf_insights_image(data)
        tweet_text = tweet_bot_logic.build_tweet_text(data, 'mtf')

        # Post to Twitter
        tweet_bot_logic.post_to_twitter(tweet_text, image_file)

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
