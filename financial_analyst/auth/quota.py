"""Daily per-user usage quotas.

Unverified accounts get stricter limits than verified ones. Limits are
adjustable through environment variables; the QuotaService accepts a
`today` callable so tests can advance the day.
"""

import os
from contextlib import closing
from datetime import date

from financial_analyst.auth.db import connect


class QuotaExceededError(Exception):
    pass


RESOURCE_ANALYSES = "analyses"
RESOURCE_CHAT = "chat"


def default_limits() -> dict:
    return {
        RESOURCE_ANALYSES: {
            "verified": int(os.getenv("QUOTA_ANALYSES_VERIFIED", "3")),
            "unverified": int(os.getenv("QUOTA_ANALYSES_UNVERIFIED", "1")),
        },
        RESOURCE_CHAT: {
            "verified": int(os.getenv("QUOTA_CHAT_VERIFIED", "30")),
            "unverified": int(os.getenv("QUOTA_CHAT_UNVERIFIED", "10")),
        },
    }


class QuotaStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with closing(connect(db_path)):
            pass

    def get_count(self, email: str, day: str, resource: str) -> int:
        with closing(connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT count FROM quota_usage WHERE email = ? AND day = ? AND resource = ?",
                (email, day, resource),
            ).fetchone()
        return row["count"] if row else 0

    def set_count(self, email: str, day: str, resource: str, count: int) -> None:
        with closing(connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO quota_usage (email, day, resource, count)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(email, day, resource) DO UPDATE SET count = excluded.count",
                (email, day, resource, count),
            )
            conn.commit()


class QuotaService:
    def __init__(self, store: QuotaStore, limits: dict | None = None, today=None) -> None:
        self.store = store
        self.limits = limits or default_limits()
        self._today = today or date.today

    def limit_for(self, user: dict, resource: str) -> int:
        tier = "verified" if user.get("verified") else "unverified"
        return self.limits[resource][tier]

    def status(self, user: dict) -> dict:
        day = self._today().isoformat()
        return {
            resource: self._usage_state(user, day, resource)
            for resource in self.limits
        }

    def consume(self, user: dict, resource: str) -> dict:
        day = self._today().isoformat()
        limit = self.limit_for(user, resource)
        used = self.store.get_count(user["email"], day, resource)
        if used >= limit:
            raise QuotaExceededError(f"Daily {resource} quota reached ({limit}).")
        self.store.set_count(user["email"], day, resource, used + 1)
        return self._usage_state(user, day, resource)

    def refund(self, user: dict, resource: str) -> None:
        day = self._today().isoformat()
        used = self.store.get_count(user["email"], day, resource)
        if used > 0:
            self.store.set_count(user["email"], day, resource, used - 1)

    def _usage_state(self, user: dict, day: str, resource: str) -> dict:
        used = self.store.get_count(user["email"], day, resource)
        limit = self.limit_for(user, resource)
        return {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
        }
