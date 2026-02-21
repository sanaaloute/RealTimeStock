"""Shared state for the master/worker agent graph."""
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage

NextWorker = Literal["scraper", "analytics", "FINISH"]


class AgentState(TypedDict, total=False):
    """State passed between supervisor and workers."""

    messages: Annotated[list[BaseMessage], "Chat messages; workers append responses."]
    next: NextWorker  # Set by supervisor; which worker to run or FINISH.
