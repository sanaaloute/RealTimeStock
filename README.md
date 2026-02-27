# RealTimeStock

## Project objective

Scrape and query BRVM (Bourse Régionale des Valeurs Mobilières) / West African stock data. A LangGraph agent coordinates scrapers (Sika Finance, Rich Bourse, BRVM) and analytics workers to answer natural-language questions via CLI or Telegram. Supports portfolio tracking and price alerts.

## Project tree

```
RealTimeStock/
├── app/
│   ├── agents/           # LangGraph agents (flattened: NLU, scraper, analytics, charts, news, portfolio)
│   │   ├── analytics_agent.py
│   │   ├── charts_agent.py
│   │   ├── graph.py
│   │   ├── llm.py
│   │   ├── news_agent.py
│   │   ├── nlu_agent.py
│   │   ├── portfolio_agent.py
│   │   ├── scraper_agent.py
│   │   ├── state.py
│   │   ├── timeseries_agent.py
│   │   └── utils.py
│   ├── api/
│   │   └── chat.py       # FastAPI: bot → API → agents (hides internal errors)
│   ├── bot/
│   │   ├── help.py
│   │   ├── redact.py
│   │   ├── telegram_bot.py
│   │   └── voice_to_text.py
│   ├── data/
│   │   ├── brvm_companies.txt
│   │   └── series/
│   ├── scrapers/
│   │   ├── base.py
│   │   ├── brvm.py
│   │   ├── brvm_announcements.py
│   │   ├── richbourse.py
│   │   ├── richbourse_news.py
│   │   ├── richbourse_timeseries.py
│   │   ├── sikafinance.py
│   │   └── sikafinance_news.py
│   ├── tools/
│   │   ├── portfolio_tools.py
│   │   ├── schemas.py
│   │   └── stock_tools.py
│   └── utils/            # Services (metrics, news, plots, user_db, etc.)
│       ├── _data.py
│       ├── brvm_basics.py
│       ├── brvm_companies.py
│       ├── comparison.py
│       ├── market_overview.py
│       ├── metrics.py
│       ├── news.py
│       ├── plots.py
│       ├── stock_metrics.py
│       ├── timeseries.py
│       └── user_db.py
├── config.py
├── run_agent.py
├── run_api.py            # Chat API (bot talks to this)
├── run_scrapers.py
├── run_telegram_bot.py
├── requirements.txt
├── requirements-docker.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set at least:

   - `TAVILY_API_KEY` — [tavily.com](https://tavily.com)

   For the agent and Telegram bot, run Ollama with a model (e.g. `ollama run glm-5:cloud` or use Ollama Cloud).

   For the Telegram bot:

   - `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `ALLOWED_TELEGRAM_IDS` — your Telegram user ID (e.g. from [@userinfobot](https://t.me/userinfobot))

3. **Run**

   ```bash
   python run_scrapers.py              # scrape sites
   python run_agent.py "Price of NTLC?" # CLI agent
   ```

   **Telegram bot** (talks to Chat API; API runs agents and hides internal errors):

   ```bash
   # Terminal 1: start the Chat API
   python run_api.py

   # Terminal 2: start the bot
   python run_telegram_bot.py
   ```

   Set `BRVM_API_URL` in `.env` if the API runs elsewhere (default `http://localhost:8000`).

   **Docker**

   ```bash
   cp .env.example .env
   # Set TELEGRAM_BOT_TOKEN, ALLOWED_TELEGRAM_IDS
   docker compose build
   docker compose up -d bot
   ```
