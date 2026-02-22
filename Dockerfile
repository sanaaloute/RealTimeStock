# Use Playwright Python image (includes Chromium and system deps; match version to requirements)
ARG PLAYWRIGHT_IMAGE=mcr.microsoft.com/playwright/python:v1.49.0-noble
FROM ${PLAYWRIGHT_IMAGE} AS base

WORKDIR /app

# Install Python deps (playwright + Chromium already in base image; use requirements-docker to avoid greenlet conflict)
COPY requirements-docker.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements-docker.txt

# App and data
COPY config.py .
COPY run_agent.py run_telegram_bot.py ./
COPY agents agents/
COPY bot bot/
COPY data data/
COPY scrapers scrapers/
COPY services services/

# Persisted at runtime via volume; ensure dir exists
RUN mkdir -p /app/data/series

# Optional: install ffmpeg for voice OGG→WAV (uncomment if you need voice messages in Telegram)
# RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default: run Telegram bot. Override to run CLI agent: python run_agent.py "query"
CMD ["python", "run_telegram_bot.py"]
