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
│   │   ├── chat.py       # FastAPI: bot → API → agents (hides internal errors)
│   │   └── whatsapp.py   # WhatsApp Business Cloud API webhook (same pipeline)
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

   **WhatsApp channel** (WhatsApp Business Cloud API — the same Chat API serves it, no extra process):

   1. Create a Meta app at [developers.facebook.com](https://developers.facebook.com), add the **WhatsApp** product, and note the *phone number ID* and a *permanent access token* (System User token).
   2. Set `WHATSAPP_VERIFY_TOKEN` (any secret you choose), `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` in `.env`.
   3. In the Meta app, configure the webhook: URL `https://<your-api-host>/whatsapp/webhook`, verify token = your `WHATSAPP_VERIFY_TOKEN`, subscribe to the `messages` field. The API must be reachable over **public HTTPS** (reverse proxy, or a tunnel like ngrok for dev).

   WhatsApp users share the Telegram pipeline: same agent, same 30/day free quota (metered as `wa:<phone>`), same memory per user. Text is answered in text; charts are sent as images. Voice/images on WhatsApp are not supported yet. Portfolio/tracking/alerts remain Telegram-only for now (WhatsApp users get a polite notice if they try).

4. **Tuning (optional, see `.env.example`)**

   - `PALMARES_CACHE_TTL_SECONDS` (default `300`) — market data (palmarès) is scraped at most once per TTL and cached in memory + on disk (`app/data/palmares_cache.json`); if a refresh fails, the last good snapshot is served so the bot keeps answering during source outages.
   - `MAX_CONCURRENT_AGENTS` (default `4`) and `AGENT_QUEUE_TIMEOUT` (default `60`) — the Chat API caps concurrent agent runs; extra requests wait, then get a friendly "busy" reply instead of overloading the LLM backend.
   - `API_SECRET_KEY` — **required for production**. The bot must send this shared secret as the `X-API-Key` header; the API rejects unauthenticated calls with 401. If empty, the API runs in dev mode (no auth). Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - `RATE_LIMIT_PER_MINUTE` (default `30`) — per-user request limit on `/chat` (0 disables).
   - `DAILY_FREE_QUOTA` (default `30`) — free requests per user per day; over-quota users get a friendly "come back tomorrow" reply. Failed requests are refunded; `QUOTA_EXEMPT_IDS` (comma-separated user ids) bypass the limit. Persisted in SQLite, so restarts don't reset it.

   Security notes: portfolio/tracking/alert tools never receive a user id from the model — the identity is injected server-side from the verified chat context, so one user cannot access another user's data. User databases (`app/data/*.db`) are git-ignored and must not be committed.

5. **Tests**

   ```bash
   python tests/test_cache_and_redact.py    # cache + formatting (no deps needed)
   python tests/test_palmares_cache.py      # market-data caching + stale warnings (no deps needed)
   python tests/test_historical_fallback.py # weekend/holiday price lookups (no deps needed)
   python tests/test_scraper_fixtures.py    # golden HTML fixtures for scraper parsers (needs full deps)
   python tests/test_portfolio_auth.py      # security: user-identity injection (needs full deps)
   python tests/test_api_security.py        # security: API key + rate limit (needs full deps)
   python tests/test_daily_quota.py         # free daily quota: limits, refunds, rollover (needs full deps)
   python tests/test_whatsapp_webhook.py    # WhatsApp channel: webhook, dedup, chunking (needs full deps)
   python tests/test_graph_e2e.py           # full graph with fake LLM (needs full deps)
   ```

   **Docker**

   ```bash
   cp .env.example .env
   # Set TELEGRAM_BOT_TOKEN, ALLOWED_TELEGRAM_IDS
   docker compose build
   docker compose up -d bot
   ```
