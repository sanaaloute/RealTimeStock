# RealTimeStock

## Project objective

Scrape and query BRVM (Bourse Régionale des Valeurs Mobilières) / West African stock data. A LangGraph agent (NLU → supervisor → 9 workers) coordinates scrapers (Sika Finance, Rich Bourse, BRVM) and analytics workers to answer natural-language questions via CLI, Telegram, or WhatsApp. Supports portfolio tracking, price alerts, predictions/trends, SGI (broker) info and company fiches.

## Project tree

```
RealTimeStock/
├── app/
│   ├── agents/           # LangGraph: NLU, supervisor, 9 workers, state
│   │   ├── graph.py             # master graph (cached compile, multi-worker routing)
│   │   ├── nlu_agent.py
│   │   ├── scraper_agent.py
│   │   ├── analytics_agent.py
│   │   ├── timeseries_agent.py
│   │   ├── charts_agent.py
│   │   ├── news_agent.py
│   │   ├── portfolio_agent.py
│   │   ├── prediction_agent.py
│   │   ├── sgi_agent.py
│   │   ├── company_details_agent.py
│   │   ├── state.py
│   │   └── utils.py
│   ├── api/
│   │   ├── chat.py       # FastAPI: bot → API → agents (auth, quota, rate limit, sanitized errors)
│   │   └── whatsapp.py   # WhatsApp Business Cloud API webhook (same pipeline)
│   ├── models/           # LLM providers: ollama | groq | openrouter
│   ├── bot/              # Telegram bot (client of the Chat API)
│   ├── data/             # BRVM_Companies.xlsx, company_details/, series/ (runtime CSVs)
│   ├── scrapers/         # Rich Bourse, Sika Finance, BRVM.org (+ dividends, trends, SGI)
│   ├── tools/            # LangChain tools + pydantic schemas
│   └── utils/            # Services (metrics, news, plots, cache, user_db, ...)
├── config.py
├── main.py               # Single entry: API + Telegram bot
├── run_agent.py          # CLI agent
├── run_api.py            # API only
├── run_telegram_bot.py   # Bot only (requires API)
├── run_scrapers.py
├── run_sgi_fetch.py      # Refresh SGI list into app/data/sgi_brvm.json
├── tests/                # Offline test suites (see below)
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
   - LLM provider: `LLM_PROVIDER=ollama|groq|openrouter` + the matching key/model (Ollama local, Ollama Cloud, Groq, or OpenRouter — see `.env.example`)

   For the Telegram bot:

   - `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `API_SECRET_KEY` — shared secret the bot sends to the Chat API (generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)

3. **Run**

   ```bash
   python run_scrapers.py              # scrape sites
   python run_agent.py "Price of NTLC?" # CLI agent
   ```

   **API + Telegram bot** (single process):

   ```bash
   python main.py
   ```

   **Or run separately** (two terminals):

   ```bash
   python run_api.py           # API only
   python run_telegram_bot.py  # Bot (requires API)
   ```

   Set `BRVM_API_URL` in `.env` if the API runs elsewhere (default `http://localhost:8000`).

   **WhatsApp channel** (WhatsApp Business Cloud API — served by the same Chat API, no extra process):

   1. Create a Meta app at [developers.facebook.com](https://developers.facebook.com), add the **WhatsApp** product, and note the *phone number ID* and a *permanent access token* (System User token).
   2. Set `WHATSAPP_VERIFY_TOKEN` (any secret you choose), `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` in `.env`.
   3. In the Meta app, configure the webhook: URL `https://<your-api-host>/whatsapp/webhook`, verify token = your `WHATSAPP_VERIFY_TOKEN`, subscribe to the `messages` field. The API must be reachable over **public HTTPS** (reverse proxy, or a tunnel like ngrok for dev).

   WhatsApp users share the Telegram pipeline: same agent, same free daily quota (metered as `wa:<phone>`), same per-user memory. Text in, text out; charts are sent as images. Voice/images on WhatsApp and portfolio/tracking/alerts on WhatsApp are not supported yet.

4. **Tuning (optional, see `.env.example`)**

   - `PALMARES_CACHE_TTL_SECONDS` (default `300`) — market data (palmarès) is scraped at most once per TTL and cached in memory + on disk (`app/data/palmares_cache.json`); if a refresh fails, the last good snapshot is served so the bot keeps answering during source outages.
   - `MAX_CONCURRENT_AGENTS` (default `4`) and `AGENT_QUEUE_TIMEOUT` (default `60`) — the Chat API caps concurrent agent runs; extra requests wait, then get a friendly "busy" reply instead of overloading the LLM backend.
   - `API_SECRET_KEY` — **required for production**. The bot must send this shared secret as the `X-API-Key` header; the API rejects unauthenticated calls with 401. If empty, the API runs in dev mode (no auth). Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - `RATE_LIMIT_PER_MINUTE` (default `30`) — per-user request limit on `/chat` (0 disables).
   - `DAILY_FREE_QUOTA` (default `30`) — free requests per user per day; over-quota users get a friendly "come back tomorrow" reply. Failed requests are refunded; `QUOTA_EXEMPT_IDS` (comma-separated user ids) bypass the limit. Persisted in SQLite, so restarts don't reset it.
   - `DATABASE_URL` — user data (portfolio, tracking, targets, quota) and chat checkpoints. Empty = local SQLite files in `app/data/` (zero config). Set `postgresql://user:password@host:5432/dbname` for PostgreSQL in production (docker compose wires this automatically via `POSTGRES_PASSWORD`).
   - `RECURSION_LIMIT` (default `100`) — max agent steps before a partial answer is returned.
   - Chat memory: checkpoints live in `app/data/chat_memory.db`, are condensed to the last user/answer pairs per thread, and the API wipes all chat memory every 15 minutes (privacy by design). `/clearmemory` clears one user's thread on demand.

   Security notes: portfolio/tracking/alert tools never receive a user id from the model — the identity is injected server-side from the verified chat context, so one user cannot access another user's data. Every reply carries an AI-generated disclaimer. User databases (`app/data/*.db`) are git-ignored and must not be committed.

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
   python tests/test_postgres_backend.py    # SQL translation always; full PG run when TEST_DATABASE_URL is set
   ```

   PostgreSQL integration check: `docker compose up -d db`, then
   `TEST_DATABASE_URL=postgresql://brvm:<password>@localhost:5432/brvm python tests/test_postgres_backend.py`.

   **Docker** — the full stack (Chat API + Telegram bot) in one command:

   ```bash
   cp .env.example .env
   # Set TELEGRAM_BOT_TOKEN, API_SECRET_KEY, POSTGRES_PASSWORD
   docker compose build
   docker compose up -d
   ```

   Services: `db` (PostgreSQL 16, data in the `postgres_data` volume), `api`, `bot`
   (both wait for the db healthcheck). To run on SQLite instead, remove
   `DATABASE_URL` from the compose services — the `bot_data` volume then holds the .db files.

   On startup each container auto-bootstraps the SGI (broker) list into the shared
   `bot_data` volume (no manual `run_sgi_fetch.py` step) and refreshes it when older
   than `SGI_REFRESH_DAYS` (default 7). A manual refresh is one command away:
   `docker compose exec api python run_sgi_fetch.py`.
