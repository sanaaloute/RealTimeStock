"""Agent helpers: current time for prompts."""
from __future__ import annotations

from datetime import datetime


def get_current_time_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_time_prefix() -> str:
    return f"Current date and time: {get_current_time_str()}"
