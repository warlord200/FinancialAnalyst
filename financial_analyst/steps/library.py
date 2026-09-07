"""Per-user saved-ticker collection, in SQLite.

The Library is the durable end product of a dossier: the tickers whose
thesis the user saved at the end of Step 6. It is private to each user, so
it lives in the per-user SQLite state layer — never in the shared draft
cache, which is keyed only by ticker and would leak one user's saves to
everyone.
"""

from contextlib import closing
from datetime import datetime, timezone

from financial_analyst.storage.sqlite import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS library (
    email TEXT NOT NULL,
    ticker TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    PRIMARY KEY (email, ticker)
);
"""


class LibraryStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with closing(connect(db_path, SCHEMA)):
            pass

    def save(self, email: str, ticker: str) -> dict:
        """Mark a ticker as saved for the user, keeping the original save
        time when it is already saved, so repeated saves are idempotent."""
        ticker = ticker.upper()
        with closing(connect(self.db_path, SCHEMA)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO library (email, ticker, saved_at)"
                " VALUES (?, ?, ?)",
                (email, ticker, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT ticker, saved_at FROM library WHERE email = ? AND ticker = ?",
                (email, ticker),
            ).fetchone()
        return {"ticker": row["ticker"], "saved_at": row["saved_at"]}

    def unsave(self, email: str, ticker: str) -> bool:
        """Remove a ticker from the user's library. Returns True when a row
        was removed and False when it was not there to begin with."""
        ticker = ticker.upper()
        with closing(connect(self.db_path, SCHEMA)) as conn:
            cursor = conn.execute(
                "DELETE FROM library WHERE email = ? AND ticker = ?",
                (email, ticker),
            )
            conn.commit()
        return cursor.rowcount > 0

    def saved_tickers(self, email: str) -> list[dict]:
        """The user's saved tickers with their save times, newest first."""
        with closing(connect(self.db_path, SCHEMA)) as conn:
            rows = conn.execute(
                "SELECT ticker, saved_at FROM library WHERE email = ?"
                " ORDER BY saved_at DESC, ticker",
                (email,),
            ).fetchall()
        return [dict(row) for row in rows]
