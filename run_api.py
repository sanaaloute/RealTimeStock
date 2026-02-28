"""Run BRVM Chat API only (no Telegram bot). For API + bot together, use: python main.py"""
import sys
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.api.chat:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
    sys.exit(0)
