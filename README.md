# Telegram Google-like Search Bot (Google Custom Search)

This repository now contains a Telegram bot that performs web searches using Google Programmable Search (Custom Search JSON API) and returns the top results to the user.

Features
- /start and /help commands
- /search <query> -> returns top 5 results (title + snippet) with buttons linking to each result

Requirements
- Python 3.8+
- TELEGRAM_TOKEN environment variable (your Telegram bot token)
- GOOGLE_API_KEY environment variable (Google Cloud API key with Custom Search enabled)
- GOOGLE_CX environment variable (Custom Search Engine ID)

Setup
1. Create a Telegram bot with @BotFather and obtain TELEGRAM_TOKEN.
2. Create a Google Cloud project and enable the Custom Search API. Obtain an API key and set GOOGLE_API_KEY.
3. Create a Programmable Search Engine (https://programmablesearchengine.google.com/) and configure it to search the entire web (see "Sites to search" -> add: "<all sites>") or customize to your needs. Get the Search Engine ID (CX) and set GOOGLE_CX.
4. Install dependencies:
   python3 -m pip install -r requirements.txt
5. Run locally:
   export TELEGRAM_TOKEN="your-telegram-token"
   export GOOGLE_API_KEY="your-google-api-key"
   export GOOGLE_CX="your-google-cx"
   python bot.py

Deployment
- The included Procfile is compatible with simple PaaS providers (Heroku, Railway):
  web: python bot.py

Security
- Never commit your tokens or API keys into the repository.
- If any key was accidentally committed, rotate it immediately and remove it from the git history.

Notes & next steps
- This is a minimal prototype. Future improvements:
  - Pagination / more results
  - Caching of recent queries
  - Support for inline queries
  - Rate-limit handling and graceful retries
