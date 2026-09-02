"""Per-user dossier step state, in SQLite.

The one-pager content is shared (it is derived from the shared numbers
layer), but the accept/reject gate on step 1 and the peer lists a user
picks for a company are private to each user.
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

PEERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS peers (
    email TEXT NOT NULL,
    ticker TEXT NOT NULL,
    position INTEGER NOT NULL,
    peer TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (email, ticker, peer)
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


class PeerStateStore:
    """Per-user peer ticker lists for each company, in SQLite.

    A user's peer choices are private state on top of the shared numbers
    layer, so this store is keyed by (email, ticker)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with closing(connect(db_path, PEERS_SCHEMA)):
            pass

    def list_peers(self, email: str, ticker: str) -> list[str]:
        with closing(connect(self.db_path, PEERS_SCHEMA)) as conn:
            rows = conn.execute(
                "SELECT peer FROM peers"
                " WHERE email = ? AND ticker = ?"
                " ORDER BY position",
                (email, ticker.upper()),
            ).fetchall()
        return [row["peer"] for row in rows]

    def set_peers(self, email: str, ticker: str, peers: list[str]) -> list[str]:
        """Replace the peer list for (email, ticker), preserving order."""
        ticker = ticker.upper()
        updated_at = datetime.now(timezone.utc).isoformat()
        with closing(connect(self.db_path, PEERS_SCHEMA)) as conn:
            conn.execute(
                "DELETE FROM peers WHERE email = ? AND ticker = ?",
                (email, ticker),
            )
            conn.executemany(
                "INSERT INTO peers (email, ticker, position, peer, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (email, ticker, position, peer, updated_at)
                    for position, peer in enumerate(peers)
                ],
            )
            conn.commit()
        return list(peers)
