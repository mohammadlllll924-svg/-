# Telegram Search Bot (Bing-backed)

This repository now contains a simple Telegram bot that performs web searches using the Bing Web Search API and returns the top results to the user.

Features
- /start and /help commands
- /search <query> -> returns top 5 results (title + snippet) with buttons linking to each result

Requirements
- Python 3.8+
- TELEGRAM_TOKEN environment variable (your Telegram bot token)
- BING_API_KEY environment variable (Azure Bing Search subscription key)

Setup
1. Create a Telegram bot with @BotFather and obtain TELEGRAM_TOKEN.
2. Create an Azure Bing Search (or Cognitive Services) resource and get the subscription key. Set it in BING_API_KEY.
3. Install dependencies:
   python3 -m pip install -r requirements.txt
4. Run locally:
   export TELEGRAM_TOKEN="your-token"
   export BING_API_KEY="your-bing-key"
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
