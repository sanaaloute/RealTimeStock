# RealTimeStock

Scrape BRVM / West African stock data from Sika Finance, Rich Bourse, and BRVM.

**Setup**

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # set TAVILY_API_KEY, optional SCRAPER_SLEEP_SECONDS
```

**Run**

```bash
python run_scrapers.py                    # all sites
python run_scrapers.py --site richbourse  # one site
python run_scrapers.py --site richbourse_timeseries --symbol NTLC   # saves data/series/NTLC_YYYY-MM-DD_YYYY-MM-DD.csv
python run_scrapers.py --json             # JSON output
```

**Sites:** `sikafinance` · `richbourse` · `richbourse_timeseries` (requires `--symbol`, writes CSV to `data/series/`) · `brvm`

**Agent (LangGraph + Ollama)**  
Master agent coordinates two workers: *scraper* (fetch palmarès, variation, timeseries, BRVM) and *analytics* (metrics, comparison, stats). Requires Ollama (e.g. `ollama run gpt-oss`).

```bash
python run_agent.py "What is the current price of NTLC?"
python run_agent.py "Compare NTLC and SLBC" --model gpt-oss
```

**Telegram bot**  
Natural-language questions; only authorized users (by Telegram user ID).

1. Create a bot with [@BotFather](https://t.me/BotFather), get the token.
2. Get your Telegram user ID (e.g. message [@userinfobot](https://t.me/userinfobot)).
3. In `.env`: set `TELEGRAM_BOT_TOKEN` and `ALLOWED_TELEGRAM_IDS=your_id` (comma-separated for multiple).
4. Run:

```bash
python run_telegram_bot.py
```

Then send a message to your bot (e.g. “What is the current price of NTLC?”).

**Docker**  
Run the Telegram bot in a container. Ollama must be reachable (on the host or in another container).

1. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_IDS`. Optionally set `OLLAMA_BASE_URL` (default in compose: `http://host.docker.internal:11434`).
2. Start Ollama on the host (e.g. `ollama run gpt-oss`).
3. Build and run:

```bash
docker compose up -d --build
```

To use a different Ollama URL (e.g. same host): `OLLAMA_BASE_URL=http://host.docker.internal:11434 docker compose up -d`.

**Troubleshooting – `telegram.error.NetworkError: httpx.ConnectError`**  
The container cannot reach Telegram’s API (api.telegram.org). Try:

1. **Test from the host:** `curl -sI https://api.telegram.org` (should return HTTP/2 200 or 404). If this fails, your network or firewall blocks Telegram.
2. **Test from the container:**  
   `docker compose run --rm bot python -c "import httpx; print(httpx.get('https://api.telegram.org', timeout=10).status_code)"`  
   If this fails but the host test works, Docker has no outbound access (e.g. firewall rules, corporate proxy).
3. **Run the bot on the host** (without Docker) to confirm the token and network work:  
   `python run_telegram_bot.py`
