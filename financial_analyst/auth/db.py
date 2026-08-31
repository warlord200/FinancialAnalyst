"""SQLite connection handling for account and quota storage.

The deployment runs the API and the background worker as separate
processes, so account state is kept in SQLite (cross-process safe) rather
than the JSON file stores used by the ingestion/numbers layers.
"""

import sqlite3

from financial_analyst.storage.sqlite import connect as sqlite_connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_usage (
    email TEXT NOT NULL,
    day TEXT NOT NULL,
    resource TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (email, day, resource)
);

CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    return sqlite_connect(db_path, SCHEMA)
