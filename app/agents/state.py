"""Shared state for the agent graph."""
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

NextWorker = Literal["scraper", "analytics", "timeseries", "charts", "news", "portfolio", "FINISH"]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], "Chat messages"]
    next: NextWorker
    image_path: str | None
    structured_data: dict[str, Any] | None
    clarification: str | None
    conversation_summary: str | None
    telegram_user_id: int | None
