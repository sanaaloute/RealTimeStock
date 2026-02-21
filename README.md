# RealTimeStock – Stock market scrapers

Web scraping tools that fetch stock market data from West African / BRVM-related sites using the **Tavily API** (extract), with configurable **sleep** between requests.

## Data sources

| Site | URL | Data |
|------|-----|------|
| **Sika Finance** | https://www.sikafinance.com/ | Indices, top gains/losses, volumes |
| **Rich Bourse** | https://www.richbourse.com/common/variation/index | Palmarès (variation, volume, value FCFA, cours) |
| **BRVM** | https://www.brvm.org/ | Official BRVM indices and stock data |

## Setup

1. **Python 3.10+**

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
   Playwright is required for Sika Finance when using non-veille periods (e.g. `--period un_mois`).

3. **Tavily API key**
   - Get a key at [tavily.com](https://tavily.com).
   - Copy `.env.example` to `.env` and set:
     ```env
     TAVILY_API_KEY=tvly-YOUR_API_KEY
     SCRAPER_SLEEP_SECONDS=2
     ```
   `SCRAPER_SLEEP_SECONDS` is the delay in seconds between each Tavily request (default: 2).

## Usage

- **Run all scrapers** (with sleep between each):
  ```bash
  python run_scrapers.py
  ```

- **Run a single site**
  ```bash
  python run_scrapers.py --site sikafinance
  python run_scrapers.py --site richbourse
  python run_scrapers.py --site brvm
  ```

- **Override sleep**
  ```bash
  python run_scrapers.py --sleep 3
  ```

- **Output JSON**
  ```bash
  python run_scrapers.py --json
  ```

## Rules

- **Sleep**: Every request uses a configurable delay (`SCRAPER_SLEEP_SECONDS` or `--sleep`) before and after the Tavily call to limit rate and be respectful to targets.
- **Tavily API**: All page content is fetched via Tavily’s `extract()` API; no direct HTTP requests to the three websites are made from this project.

## Project layout

```
RealTimeStock/
├── config.py           # TAVILY_API_KEY, SLEEP_SECONDS, URLs
├── run_scrapers.py     # CLI: run one or all scrapers
├── scrapers/
│   ├── base.py        # BaseScraper (Tavily client + sleep + extract_content)
│   ├── sikafinance.py # SikaFinanceScraper
│   ├── richbourse.py  # RichBourseScraper
│   └── brvm.py        # BRVMScraper
├── requirements.txt
├── .env.example
└── README.md
```

## Output shape (example)

- **sikafinance**: `indices`, `top_gains`, `top_losses`, `raw_preview`
- **richbourse**: `date`, `stocks` (symbol, name, variation_pct, volume, value_fcfa, cours_actuel, cours_veille), `summary`, `raw_preview`
- **brvm**: `indices`, `stocks`, `raw_preview`

Parsing depends on the structure of the content returned by Tavily; you may need to adjust regex/BeautifulSoup logic if the sites change.
