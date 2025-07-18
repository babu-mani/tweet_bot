# Market Update Twitter Bot

A fully automated Python bot that fetches daily financial data, generates custom summary images, and posts them to a Twitter account.

---

## Features

-   **Global Market Update**: Fetches the latest data for GIFT NIFTY, Dow Jones, Nasdaq, and other major world indices.
-   **MTF Insights**: Scrapes Margin Trading Facility (MTF) data.
-   **Image Generation**: Creates professional-looking images for each update using the Pillow library.
-   **Automation**: Uses GitHub Actions to run automatically on a schedule, completely free for public repositories.
-   **Secure**: Manages all API credentials securely using GitHub's encrypted secrets.

---

## Automation Schedule

This bot is configured to run via two separate GitHub Actions workflows:

1.  **Global Market Update**: Runs daily at **8:30 AM IST** (03:00 UTC).
2.  **MTF Insights Update**: Runs daily at **8:45 AM IST** (03:15 UTC).

---

## Project Structure


.
├── .github/
│   └── workflows/
│       ├── global-update.yml
│       └── mtf-update.yml
├── font/
│   └── Roboto-Bold.ttf
├── .gitignore
├── market_bot.py
├── README.md
└── requirements.txt

