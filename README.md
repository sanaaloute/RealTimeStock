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
Master agent coordinates two workers: *scraper* (fetch palmarès, variation, timeseries, BRVM) and *analytics* (metrics, comparison, stats). Requires Ollama (e.g. `ollama run qwen3:8b`).

```bash
python run_agent.py "What is the current price of NTLC?"
python run_agent.py "Compare NTLC and SLBC" --model qwen3:8b
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

**Portfolio, tracking and price alerts**  
Bot users can manage a BRVM portfolio (add/remove positions, see growth/loss), a tracking list, and price alerts. Data: `data/brvm_bot.db`. Examples: "Show my portfolio", "Add NTLC at 50000 on 2025-01-15", "Notify me when NTLC reaches 55000". Target alerts are checked every 5 minutes.

**Docker**  
Build and run the Telegram bot (and optionally Ollama) with Docker Compose.

1. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` and `ALLOWED_TELEGRAM_IDS`.
2. **Ollama:** either run Ollama on the host and set in `.env`:  
   `OLLAMA_BASE_URL=http://host.docker.internal:11434`  
   or use the Compose Ollama service and set:  
   `OLLAMA_BASE_URL=http://ollama:11434`
3. Build and run:

```bash
docker compose build
docker compose up -d bot          # bot only (Ollama on host)
# or
docker compose up -d              # bot + ollama (then: docker compose exec ollama ollama pull qwen3:8b)
```

Time series CSVs are stored in a Docker volume (`bot_data`). For voice messages in the bot, uncomment the ffmpeg line in the Dockerfile and rebuild (requires apt to be available in the image).

**Troubleshooting – Ollama 503 (Service Unavailable)**  
- **Bot run with `python run_telegram_bot.py` (on the host):** The bot must use localhost. In `.env` set `OLLAMA_BASE_URL=http://127.0.0.1:11434` or **remove/comment out** `OLLAMA_BASE_URL` so it defaults to localhost. Do **not** use `host.docker.internal` when the bot runs on the host.  
- **Bot in Docker, Ollama on host:** In `.env` use `OLLAMA_BASE_URL=http://host.docker.internal:11434`. If the log shows `http://ollama:11434`, change it to `host.docker.internal`.  
- **Ollama only listening on localhost:** By default Ollama binds to 127.0.0.1, so Docker may get 503 when calling the host. On the **host** set `OLLAMA_HOST=0.0.0.0` and restart Ollama. Linux (systemd): `sudo mkdir -p /etc/systemd/system/ollama.service.d && echo -e '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"' | sudo tee /etc/systemd/system/ollama.service.d/override.conf` then `sudo systemctl daemon-reload && sudo systemctl restart ollama`. Windows/Mac: set the env var in your shell or in Ollama’s config, then restart Ollama.  
- **Model not loaded:** On the host run `ollama pull qwen3:8b` then `ollama run qwen3:8b` (Ctrl+C after it loads). Check `curl http://127.0.0.1:11434/api/tags` lists the model, then retry the bot.

**Troubleshooting – `telegram.error.NetworkError: httpx.ConnectError`**  
The container cannot reach Telegram’s API (api.telegram.org). Try:

1. **Test from the host:** `curl -sI https://api.telegram.org` (should return HTTP/2 200 or 404). If this fails, your network or firewall blocks Telegram.
2. **Test from the container:**  
   `docker compose run --rm bot python -c "import httpx; print(httpx.get('https://api.telegram.org', timeout=10).status_code)"`  
   If this fails but the host test works, Docker has no outbound access (e.g. firewall rules, corporate proxy).
3. **Run the bot on the host** (without Docker) to confirm the token and network work:  
   `python run_telegram_bot.py`
