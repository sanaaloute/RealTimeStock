"""Shared state for the master/worker agent graph."""
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage

NextWorker = Literal["scraper", "analytics", "timeseries", "charts", "news", "FINISH"]


class AgentState(TypedDict, total=False):
    """State passed between supervisor and workers."""

    messages: Annotated[list[BaseMessage], "Chat messages; workers append responses."]
    next: NextWorker  # Set by supervisor; which worker to run or FINISH.
    image_path: str | None  # Set by charts worker when a plot was generated; bot sends as photo.
    # NLU: extracted intent + entities for downstream workers; or clarification question for the user.
    structured_data: dict[str, Any] | None  # intent, entities, suggested_worker when clear.
    clarification: str | None  # When set, NLU asks user to clarify; bot returns this and ends.
    # Summarize memory: condensed summary of older conversation when message count is high.
    conversation_summary: str | None
