"""Shared helpers for agents: current time, message summarizer for memory."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


def get_current_time_str() -> str:
    """Current date and time for injection into prompts. Use this so agents know the current time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_time_prefix() -> str:
    """Line to prepend to system prompts: current date and time."""
    return f"Current date and time: {get_current_time_str()}"
