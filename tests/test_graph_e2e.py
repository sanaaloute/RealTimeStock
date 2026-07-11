"""End-to-end smoke test of the master LangGraph with a fake LLM.

Validates under the installed langgraph version:
1. Full flow NLU -> supervisor -> portfolio worker -> injected identity -> DB write.
2. Track A: supervisor early-FINISH (exactly 3 LLM calls, not 4+).
3. Track A: get_compiled_graph caches compiled graphs per (model, checkpointer).
4. Track B: the portfolio write lands on the verified telegram_user_id.

Run:
    .venv/Scripts/python tests/test_graph_e2e.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from app.utils import user_db  # noqa: E402

USER_ID = 123
LLM_CALLS = {"n": 0}


class ToolFriendlyFake(GenericFakeChatModel):
    """GenericFakeChatModel that accepts bind_tools (ignores them)."""

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        LLM_CALLS["n"] += 1
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _make_fake():
    return ToolFriendlyFake(
        messages=iter(
            [
                # 1) NLU: structured intent
                AIMessage(
                    content='{"intent": "portfolio_add", "entities": {"symbol": "NTLC", '
                    '"buy_price": 50000, "buy_date": "2025-01-15"}, "suggested_worker": "portfolio"}'
                ),
                # 2) Portfolio worker: tool call
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "portfolio_add",
                            "args": {"symbol": "NTLC", "buy_price": 50000, "buy_date": "2025-01-15"},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                # 3) Portfolio worker: final answer
                AIMessage(content="Added NTLC to your portfolio."),
            ]
        )
    )


def _patch_llm(fake):
    """Point every get_llm consumer at the fake model."""
    import app.agents.graph as graph_mod
    import app.agents.nlu_agent as nlu_mod
    import app.agents.analytics_agent as analytics_mod
    import app.agents.scraper_agent as scraper_mod
    import app.agents.timeseries_agent as timeseries_mod
    import app.agents.charts_agent as charts_mod
    import app.agents.news_agent as news_mod
    import app.agents.portfolio_agent as portfolio_mod

    for mod in (graph_mod, nlu_mod, analytics_mod, scraper_mod, timeseries_mod,
                charts_mod, news_mod, portfolio_mod):
        mod.get_llm = lambda *a, **k: fake


def test_full_portfolio_flow_and_early_finish():
    user_db.DB_PATH = Path(tempfile.mkdtemp()) / "e2e.db"
    user_db.init_db()
    LLM_CALLS["n"] = 0
    _patch_llm(_make_fake())

    from app.agents.graph import run_agent

    result = run_agent(
        "I bought NTLC at 50000 on 2025-01-15",
        model="fake",
        thread_id="e2e",
        telegram_user_id=USER_ID,
        checkpointer=MemorySaver(),
    )
    last = result["messages"][-1].content
    assert "portfolio" in last.lower(), last
    positions = user_db.portfolio_list(USER_ID)
    assert len(positions) == 1 and positions[0]["symbol"] == "NTLC", positions
    # NLU (1) + worker x2 = 3. A redundant supervisor routing call would make it 4.
    assert LLM_CALLS["n"] == 3, f"expected 3 LLM calls, got {LLM_CALLS['n']}"


def test_compiled_graph_is_cached():
    _patch_llm(_make_fake())
    from app.agents.graph import get_compiled_graph

    cp = MemorySaver()
    g1 = get_compiled_graph("fake", cp)
    g2 = get_compiled_graph("fake", cp)
    assert g1 is g2, "graph must be compiled once per (model, checkpointer)"
    cp2 = MemorySaver()
    g3 = get_compiled_graph("fake", cp2)
    assert g3 is not g1, "different checkpointer -> different graph"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
