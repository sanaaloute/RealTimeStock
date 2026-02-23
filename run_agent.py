"""
Run the master agent (LangGraph: supervisor + scraper / analytics workers).

Requires Ollama with a model (e.g. ollama run qwen3:8b).
Chat memory persists in data/chat_memory.db (use --no-memory to skip).

  python run_agent.py "What is the current price of NTLC?"
  python run_agent.py "Compare NTLC and SLBC"
  python run_agent.py --model qwen3:8b "Get Rich Bourse palmarès for last week"
  python run_agent.py --no-memory "One-off query without history"
"""
import argparse
import sys

from agents import run_agent
from agents.graph import CHAT_MEMORY_DB


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BRVM stock master agent (scraper + analytics workers).")
    parser.add_argument("query", nargs="?", default="", help="User question (or read from stdin).")
    parser.add_argument("--model", default="qwen3:8b", help="Ollama model name (default: qwen3:8b).")
    parser.add_argument("--no-memory", action="store_true", help="Disable persistent chat memory for this run.")
    args = parser.parse_args()

    text = (args.query or "").strip()
    if not text and sys.stdin.isatty():
        parser.print_help()
        return 0
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        return 1

    print("Running agent...")
    if args.no_memory:
        result = run_agent(text, model=args.model, thread_id="cli")
    else:
        CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        from langgraph.checkpoint.sqlite import SqliteSaver
        with SqliteSaver.from_conn_string(str(CHAT_MEMORY_DB)) as checkpointer:
            result = run_agent(text, model=args.model, thread_id="cli", checkpointer=checkpointer)
    messages = result.get("messages") or []
    for m in messages:
        if hasattr(m, "content") and m.content:
            role = getattr(m, "type", "message")
            print(f"\n[{role}]\n{m.content}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
