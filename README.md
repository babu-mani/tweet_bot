# 📈 Automated Financial Market Update Twitter Bot

A Python-powered bot that fetches live market data, generates image summaries, and posts them to Twitter — all on a fixed daily schedule. It provides updates on global indices and Margin Trading Facility (MTF) insights, perfect for traders and market watchers.

---

## ✨ Highlights

- **Global Market Data**: GIFT NIFTY, Nikkei 225, Dow Futures, S&P 500, Nasdaq, Hang Seng  
- **MTF Insights**: Positions Added/Liquidated, Net Book, Total Industry Book  
- **Image Generation**: Clean, auto-generated visuals using Pillow  
- **Twitter Automation**: Posts directly using Twitter API  
- **Serverless Hosting**: Deployed on [Vercel](https://vercel.com)  
- **Cron Scheduling**: Triggered daily via [cron-job.org](https://cron-job.org)

---

## ⚙️ How It Works

cron-job.org → Vercel API Endpoint → Python Script → Tweet


- `index.py` (Flask app) handles data fetch, image creation, and posting  
- Hosted as a **serverless function** — no server maintenance  
- Two endpoints:
  - `/global-market-update` (8:30 AM IST)
  - `/mtf-insights-update` (8:45 AM IST)

---

## 🚀 Quick Setup

### 1. Deploy to Vercel

- Fork this repo to your GitHub account  
- Import the repo into [Vercel](https://vercel.com)  
- Add the following **Environment Variables**:

TWITTER_API_KEY
TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_TOKEN_SECRET


- Deploy and note your Vercel domain (e.g., `https://your-bot.vercel.app`)

---

### 2. Schedule with cron-job.org

Create two cron jobs on [cron-job.org](https://cron-job.org):

#### Global Market Update
- **URL**: `https://your-bot.vercel.app/global-market-update`
- **Time**: `0 3 * * *` (8:30 AM IST)

#### MTF Insights Update
- **URL**: `https://your-bot.vercel.app/mtf-insights-update`
- **Time**: `15 3 * * *` (8:45 AM IST)

---

## 🔧 Customization

- ⏰ Adjust schedule on cron-job.org  
- 🎨 Tweak visuals in `create_market_update_image()`  
- 📝 Change tweet text in `build_tweet_text()`  
- 📊 Add or replace data sources in `index.py`

---

## 👤 Author

**ChartWizMani**  
📊 Twitter: [@ChartWizMani](https://twitter.com/ChartWizMani)

