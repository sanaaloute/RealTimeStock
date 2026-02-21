# RealTimeStock: Telegram bot + BRVM agent (Ollama on host or separate service)
FROM python:3.11-slim

WORKDIR /app

# Install dependencies (Playwright optional; omit for smaller image if only bot+analytics)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY config.py .
COPY run_telegram_bot.py .
COPY agents/ agents/
COPY bot/ bot/
COPY scrapers/ scrapers/
COPY services/ services/

# Create data dir for timeseries CSV if mounted
RUN mkdir -p data/series

# Default: run Telegram bot. Override to run scrapers or CLI agent.
CMD ["python", "-u", "run_telegram_bot.py"]
