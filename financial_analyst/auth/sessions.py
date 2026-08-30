"""Revoked (logged-out) JWT denylist.

Stateless JWTs can't be invalidated by the client alone, so logout records
the token's id until its natural expiry. Rows are pruned lazily when a
revoked token is checked or a new one is inserted.
"""

from contextlib import closing
from datetime import datetime, timezone

from financial_analyst.auth.db import connect


class RevokedTokenStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with closing(connect(db_path)):
            pass

    def revoke(self, jti: str, expires_at: str) -> None:
        with closing(connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)",
                (jti, expires_at),
            )
            conn.commit()

    def is_revoked(self, jti: str) -> bool:
        self._prune_expired()
        with closing(connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT jti FROM revoked_tokens WHERE jti = ?", (jti,)
            ).fetchone()
        return row is not None

    def _prune_expired(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(connect(self.db_path)) as conn:
            conn.execute("DELETE FROM revoked_tokens WHERE expires_at <= ?", (now,))
            conn.commit()
