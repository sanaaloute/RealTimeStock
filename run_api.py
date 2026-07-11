"""Run BRVM Chat API (uvicorn on port 8000)."""
import logging
import sys

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

if __name__ == "__main__":
    uvicorn.run(
        "app.api.chat:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
    sys.exit(0)
