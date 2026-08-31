"""Per-user dossier step state, in SQLite.

The one-pager content is shared (it is derived from the shared numbers
layer), but the accept/reject gate on step 1 is private to each user.
"""

from contextlib import closing
from datetime import datetime, timezone

from financial_analyst.storage.sqlite import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS step_gates (
    email TEXT NOT NULL,
    ticker TEXT NOT NULL,
    step INTEGER NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (email, ticker, step)
);
"""


class StepStateStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with closing(connect(db_path, SCHEMA)):
            pass

    def get_gate(self, email: str, ticker: str, step: int) -> dict | None:
        with closing(connect(self.db_path, SCHEMA)) as conn:
            row = conn.execute(
                "SELECT step, status, updated_at FROM step_gates"
                " WHERE email = ? AND ticker = ? AND step = ?",
                (email, ticker.upper(), step),
            ).fetchone()
        if row is None:
            return None
        return {
            "step": row["step"],
            "status": row["status"],
            "updated_at": row["updated_at"],
        }

    def set_gate(self, email: str, ticker: str, step: int, status: str) -> dict:
        updated_at = datetime.now(timezone.utc).isoformat()
        with closing(connect(self.db_path, SCHEMA)) as conn:
            conn.execute(
                "INSERT INTO step_gates (email, ticker, step, status, updated_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(email, ticker, step)"
                " DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
                (email, ticker.upper(), step, status, updated_at),
            )
            conn.commit()
        return {"step": step, "status": status, "updated_at": updated_at}
