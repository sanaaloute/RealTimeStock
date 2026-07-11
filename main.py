"""Single entry point: runs API + Telegram bot. Usage: python main.py"""
import sys
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
    sys.exit(0)
