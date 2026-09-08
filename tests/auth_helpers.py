"""Shared auth/quota setup for HTTP API tests.

T3 added auth and per-user quotas to the FastAPI app, so any test that
hits a gated endpoint must wire real auth/quota services against temp-dir
SQLite files and sign in a user. This keeps that boilerplate in one place.
"""

import os

from fastapi.testclient import TestClient

import api.main as main
from financial_analyst.auth.quota import QuotaService, QuotaStore
from financial_analyst.auth.sessions import RevokedTokenStore
from financial_analyst.auth.users import AuthService, UserStore

TEST_SECRET = "test-secret-key-that-is-longer-than-32-bytes"

# Generous limits so tests about other concerns never trip a quota.
GENEROUS_LIMITS = {
    "analyses": {"verified": 100, "unverified": 100},
    "chat": {"verified": 100, "unverified": 100},
}

# The built-in limits quota.default_limits() returns when no QUOTA_* env vars
# are set. Tests that mean "use the built-in defaults" must be hermetic: a
# dev .env (or a pytest plugin that auto-loads it) must not change them.
QUOTA_ENV_VARS = (
    "QUOTA_ANALYSES_VERIFIED",
    "QUOTA_ANALYSES_UNVERIFIED",
    "QUOTA_CHAT_VERIFIED",
    "QUOTA_CHAT_UNVERIFIED",
)


def builtin_limits() -> dict:
    """Snapshot quota.default_limits() as if no QUOTA_* env vars were set."""
    from financial_analyst.auth.quota import default_limits

    saved = {name: os.environ.pop(name, None) for name in QUOTA_ENV_VARS}
    try:
        return default_limits()
    finally:
        for name, value in saved.items():
            if value is not None:
                os.environ[name] = value


def make_auth_services(tmp_path, limits=None, today=None):
    if limits is None:
        limits = builtin_limits()
    db = str(tmp_path / "storage" / "auth.db")
    auth = AuthService(
        UserStore(db),
        secret=TEST_SECRET,
        revoked_store=RevokedTokenStore(db),
    )
    quota = QuotaService(
        QuotaStore(str(tmp_path / "storage" / "quota.db")),
        limits=limits,
        today=today,
    )
    return auth, quota


def wire_auth(monkeypatch, auth, quota):
    monkeypatch.setattr(main, "_get_auth_service", lambda: auth)
    monkeypatch.setattr(main, "_get_quota_service", lambda: quota)


def build_client(tmp_path, monkeypatch, limits=None, today=None):
    auth, quota = make_auth_services(tmp_path, limits=limits, today=today)
    wire_auth(monkeypatch, auth, quota)
    client = TestClient(main.create_app())
    return client, auth, quota


def signup_and_auth(client, email="tester@example.com", password="password123") -> str:
    resp = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return token
