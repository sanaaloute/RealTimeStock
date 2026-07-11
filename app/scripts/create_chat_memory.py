"""Create chat_memory.db with the LangGraph checkpoint schema. Run: python -m app.scripts.create_chat_memory

When DATABASE_URL is set (PostgreSQL), creates the checkpoint tables there instead.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# app/scripts/create_chat_memory.py -> app/data/chat_memory.db
APP_DIR = Path(__file__).resolve().parent.parent
CHAT_MEMORY_DB = APP_DIR / "data" / "chat_memory.db"

try:
    import config

    DATABASE_URL = getattr(config, "DATABASE_URL", "")
except Exception:
    DATABASE_URL = ""

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BLOB,
    metadata BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE IF NOT EXISTS writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
"""


def main() -> int:
    if DATABASE_URL:
        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver

        with psycopg.connect(DATABASE_URL) as conn:
            PostgresSaver(conn).setup()
        print("Created checkpoint tables in PostgreSQL:", DATABASE_URL.split("@")[-1])
        return 0
    CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(CHAT_MEMORY_DB)) as conn:
        conn.executescript(SCHEMA)
    print("Created:", CHAT_MEMORY_DB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
