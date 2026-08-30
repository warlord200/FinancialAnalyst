"""Shared auth/quota setup for HTTP API tests.

T3 added auth and per-user quotas to the FastAPI app, so any test that
hits a gated endpoint must wire real auth/quota services against temp-dir
SQLite files and sign in a user. This keeps that boilerplate in one place.
"""

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


def make_auth_services(tmp_path, limits=None, today=None):
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
