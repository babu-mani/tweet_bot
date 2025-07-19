📈 Automated Financial Market Update Twitter Bot
This project deploys a Python-based Twitter bot that automatically fetches live financial market data, generates informative images, and posts them to Twitter on a predefined schedule. It provides timely updates on global indices and MTF (Margin Trading Facility) insights.

✨ Features
Global Market Updates: Fetches real-time data for GIFT NIFTY, Nikkei 225, Dow Jones Futures, S&P 500, Nasdaq, and Hang Seng.

MTF Insights: Scrapes and presents key Margin Trading Facility insights (Positions Added, Liquidated, Net Book Added, Industry MTF Book).

Dynamic Image Generation: Creates visually appealing images summarizing market data and MTF insights using PIL (Pillow).

Automated Twitter Posting: Integrates with the Twitter API to post generated images and accompanying text.

Serverless Deployment: Hosted on Vercel as a serverless function, ensuring cost-efficiency and scalability.

External Scheduling: Utilizes cron-job.org for reliable and precise scheduling of daily posts, eliminating the need for a continuously running local machine.

🚀 Architecture & How it Works
The bot operates on a robust, serverless architecture:

Python Script (api/index.py): Contains all the core logic for data fetching, image processing, tweet text generation, and interaction with the Twitter API. It's built as a Flask application, exposing specific API endpoints for market updates and MTF insights.

Vercel Deployment: The entire Python application is deployed as a serverless function on Vercel. Vercel handles the hosting, scaling, and execution of the Python code when its endpoints are triggered.

cron-job.org Scheduling: cron-job.org is used as an external cron service. It sends HTTP GET requests to the specific Vercel API endpoints (/global-market-update and /mtf-insights-update) at the exact scheduled times (e.g., daily at 8:30 AM IST).

Twitter API: Upon receiving a trigger, the Vercel serverless function executes the Python code, fetches data, creates an image, and posts it to Twitter using your configured API credentials.

🛠️ Setup & Deployment for Others
Follow these steps to deploy and automate your own instance of this bot:

Prerequisites
A GitHub account.

A Vercel account (connected to your GitHub).

A cron-job.org account.

Twitter Developer Account with API v1.1 and v2 access (Consumer Keys, Access Tokens, etc.).

Step 1: Prepare Your GitHub Repository
Fork this Repository:

Go to the original repository on GitHub.

Click the "Fork" button in the top right corner. This creates a copy of the repository under your GitHub account.

Verify Repository Structure:

Ensure your forked repository has the following structure. All necessary files are already in place:

your-tweet-bot-repo/
├── api/
│   ├── index.py           # Consolidated bot logic and Flask app
│   └── Roboto-Bold.ttf    # Font file used for image generation
├── requirements.txt       # Python dependencies
└── (other files like README.md, .gitignore, etc.)

Important: Confirm that api/tweet_bot_logic.py does not exist, and Roboto-Bold.ttf is directly inside the api/ folder (not in api/font/). Also, ensure there is no vercel.json file in the root, as Vercel will auto-detect the setup.

Step 2: Deploy to Vercel
Import Project:

Go to your Vercel Dashboard.

Click "New Project."

Select your forked tweet_bot repository from your GitHub account.

Configure Environment Variables:

This is CRUCIAL. Your bot needs Twitter API keys and tokens.

During the import process (or later via Project Settings -> Environment Variables), add the following:

TWITTER_API_KEY: Your Twitter API Key

TWITTER_API_SECRET: Your Twitter API Secret

TWITTER_ACCESS_TOKEN: Your Twitter Access Token

TWITTER_ACCESS_TOKEN_SECRET: Your Twitter Access Token Secret

Provide your actual secret values for each.

Deploy: Click "Deploy." Vercel will automatically build and deploy your Python Flask application.

Get Domain: Once deployed, note down your primary Vercel domain (e.g., https://your-project-name.vercel.app). You can test it by visiting https://your-project-name.vercel.app/ in your browser; it should show {"status": "ok", "message": "Tweet Bot API is running!"}.

Step 3: Set Up Scheduling with cron-job.org
Login: Go to cron-job.org and log in or register for a free account.

Create "Global Market Update Bot" Cronjob:

Click "Create cronjob."

Title: Global Market Update Bot

URL: https://your-vercel-domain.vercel.app/global-market-update (Replace your-vercel-domain.vercel.app with your actual Vercel domain).

Schedule (Custom): 0 3 * * * (This means 0 minutes past 3 AM UTC, which is 8:30 AM IST).

Ensure (UTC) Coordinated Universal Time is selected as the timezone.

Enable "Save responses in job history" and any desired notifications.

Click "CREATE."

Create "MTF Insights Bot" Cronjob:

Click "Create cronjob" again.

Title: MTF Insights Bot

URL: https://your-vercel-domain.vercel.app/mtf-insights-update (Replace with your actual Vercel domain).

Schedule (Custom): 15 3 * * * (This means 15 minutes past 3 AM UTC, which is 8:45 AM IST).

Ensure (UTC) Coordinated Universal Time is selected as the timezone.

Enable "Save responses in job history" and any desired notifications.

Click "CREATE."

🚀 Usage
Once configured, your bot will automatically:

Fetch global market data and post to Twitter daily at 8:30 AM IST.

Fetch MTF insights and post to Twitter daily at 8:45 AM IST.

You can monitor job execution and success/failure in the "History" section of each cronjob on cron-job.org.

⚙️ Customization
Schedule: Adjust the cron expressions on cron-job.org to change the posting times.

Data Sources: Modify the fetch_gift_nifty, get_yfinance_data, and fetch_mtf_data functions in api/index.py to integrate different data sources.

Image Design: Customize the create_market_update_image and create_mtf_insights_image functions in api/index.py to change the visual appearance of the generated images.

Tweet Content: Modify the build_tweet_text function to change the accompanying tweet messages and hashtags.

🧑‍💻 Author
ChartWizMani
