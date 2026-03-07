"""Create chat_memory.db with the LangGraph checkpoint schema. Run: python -m app.scripts.create_chat_memory"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# app/scripts/create_chat_memory.py -> app/data/chat_memory.db
APP_DIR = Path(__file__).resolve().parent.parent
CHAT_MEMORY_DB = APP_DIR / "data" / "chat_memory.db"

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
    CHAT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(CHAT_MEMORY_DB)) as conn:
        conn.executescript(SCHEMA)
    print("Created:", CHAT_MEMORY_DB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
