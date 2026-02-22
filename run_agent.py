"""
Run the master agent (LangGraph: supervisor + scraper / analytics workers).

Requires Ollama with a model (e.g. ollama run qwen3:8b).

  python run_agent.py "What is the current price of NTLC?"
  python run_agent.py "Compare NTLC and SLBC"
  python run_agent.py --model qwen3:8b "Get Rich Bourse palmarès for last week"
"""
import argparse
import sys

from agents import run_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BRVM stock master agent (scraper + analytics workers).")
    parser.add_argument("query", nargs="?", default="", help="User question (or read from stdin).")
    parser.add_argument("--model", default="qwen3:8b", help="Ollama model name (default: qwen3:8b).")
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
    result = run_agent(text, model=args.model)
    messages = result.get("messages") or []
    for m in messages:
        if hasattr(m, "content") and m.content:
            role = getattr(m, "type", "message")
            print(f"\n[{role}]\n{m.content}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
