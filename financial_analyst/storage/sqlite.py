"""SQLite connection handling shared across the per-user stores.

The deployment runs the API and the background worker as separate
processes, so per-user and account state lives in SQLite (cross-process
safe) rather than the JSON file stores used by the shared-content layers.
"""

import sqlite3
from pathlib import Path


def connect(db_path: str, schema: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(schema)
    conn.commit()
    return conn
