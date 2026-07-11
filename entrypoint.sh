#!/bin/sh
# Container entrypoint: best-effort SGI (broker) data bootstrap, then run the real command.
#
# Populates app/data/sgi_brvm.json when missing or older than SGI_REFRESH_DAYS
# (default 7), so no manual `python run_sgi_fetch.py` step is needed after deploy.
# Never blocks startup: if the fetch fails, SGI answers degrade gracefully.
set -e

DATA_DIR="${BOT_DATA_DIR:-/app/app/data}"
SGI_JSON="${SGI_JSON_PATH:-$DATA_DIR/sgi_brvm.json}"
DAYS="${SGI_REFRESH_DAYS:-7}"

mkdir -p "$DATA_DIR"

stale=0
if [ ! -s "$SGI_JSON" ]; then
  stale=1
elif find "$SGI_JSON" -mtime +"$DAYS" 2>/dev/null | grep -q .; then
  stale=1
fi

if [ "$stale" = "1" ]; then
  echo "[entrypoint] SGI data missing or older than ${DAYS}d - fetching (best effort)..."
  # flock: api + bot share the data volume and may boot together on first deploy.
  if command -v flock >/dev/null 2>&1; then
    flock "$DATA_DIR/.sgi.lock" python run_sgi_fetch.py \
      || echo "[entrypoint] WARNING: SGI fetch failed (non-fatal); SGI answers may be limited."
  else
    python run_sgi_fetch.py \
      || echo "[entrypoint] WARNING: SGI fetch failed (non-fatal); SGI answers may be limited."
  fi
fi

exec "$@"
