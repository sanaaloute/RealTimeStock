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
python run_scrapers.py --site richbourse_mouvements --symbol NTLC
python run_scrapers.py --json             # JSON output
```

**Sites:** `sikafinance` · `richbourse` · `richbourse_mouvements` (requires `--symbol`) · `brvm`
