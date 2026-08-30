from datetime import date

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import api.main as main
from tests.auth_helpers import build_client


def make_client(tmp_path, monkeypatch, today=None, limits=None):
    return build_client(tmp_path, monkeypatch, limits=limits, today=today)


def signup(client, email="alice@example.com", password="password123"):
    resp = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_numbers_client(tmp_path, monkeypatch, today=None, limits=None):
    client, auth, _ = make_client(tmp_path, monkeypatch, today=today, limits=limits)
    fake = MagicMock(refresh=MagicMock(return_value={"ticker": "TSLA", "ok": True}))
    monkeypatch.setattr(main, "_get_numbers_service", lambda: fake)
    return client, auth, fake


class TestSignup:
    def test_signup_returns_token_and_unverified_user(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.post(
            "/api/auth/signup", json={"email": "alice@example.com", "password": "password123"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token"]
        assert body["user"]["email"] == "alice@example.com"
        assert body["user"]["verified"] is False

    def test_signup_rejects_invalid_email(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.post("/api/auth/signup", json={"email": "not-an-email", "password": "password123"})
        assert resp.status_code == 400

    def test_signup_rejects_short_password(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.post("/api/auth/signup", json={"email": "alice@example.com", "password": "short"})
        assert resp.status_code == 400

    def test_signup_rejects_duplicate_email(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        signup(client)
        resp = client.post(
            "/api/auth/signup", json={"email": "alice@example.com", "password": "password123"}
        )
        assert resp.status_code == 400

    def test_signup_is_case_insensitive_on_email(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        signup(client, email="Alice@Example.com")
        resp = client.post(
            "/api/auth/signup", json={"email": "alice@example.com", "password": "password123"}
        )
        assert resp.status_code == 400


class TestLogin:
    def test_login_returns_token_for_valid_credentials(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        signup(client)
        resp = client.post(
            "/api/auth/login", json={"email": "alice@example.com", "password": "password123"}
        )
        assert resp.status_code == 200
        assert resp.json()["token"]

    def test_login_rejects_wrong_password(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        signup(client)
        resp = client.post(
            "/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"}
        )
        assert resp.status_code == 401

    def test_login_rejects_unknown_email(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": "password123"}
        )
        assert resp.status_code == 401


class TestMeLogout:
    def test_me_returns_current_user(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        token = signup(client)
        resp = client.get("/api/auth/me", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"
        assert resp.json()["verified"] is False

    def test_me_rejects_missing_token(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        assert client.get("/api/auth/me").status_code == 401

    def test_me_rejects_garbage_token(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.get("/api/auth/me", headers=auth("not-a-real-token"))
        assert resp.status_code == 401

    def test_logout_requires_auth_and_succeeds(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        assert client.post("/api/auth/logout").status_code == 401
        token = signup(client)
        assert client.post("/api/auth/logout", headers=auth(token)).status_code == 200

    def test_logout_revokes_token(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        token = signup(client)
        assert client.get("/api/auth/me", headers=auth(token)).status_code == 200
        client.post("/api/auth/logout", headers=auth(token))
        assert client.get("/api/auth/me", headers=auth(token)).status_code == 401

    def test_verify_upgrades_account(self, tmp_path, monkeypatch):
        client, auth_svc, _ = make_client(tmp_path, monkeypatch)
        token = signup(client)
        assert client.get("/api/auth/me", headers=auth(token)).json()["verified"] is False
        auth_svc.verify("alice@example.com")
        assert client.get("/api/auth/me", headers=auth(token)).json()["verified"] is True


class TestQuota:
    def test_quota_endpoint_reports_usage_and_limits(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        token = signup(client)
        resp = client.get("/api/auth/quota", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["analyses"] == {"used": 0, "limit": 1, "remaining": 1}
        assert body["chat"] == {"used": 0, "limit": 10, "remaining": 10}

    def test_unverified_account_gets_stricter_analysis_quota(self, tmp_path, monkeypatch):
        client, _, fake = make_numbers_client(tmp_path, monkeypatch)
        token = signup(client)
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 200
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 429
        assert fake.refresh.call_count == 1

    def test_verified_account_gets_higher_analysis_quota(self, tmp_path, monkeypatch):
        client, auth_svc, fake = make_numbers_client(tmp_path, monkeypatch)
        token = signup(client)
        auth_svc.verify("alice@example.com")
        for _ in range(3):
            assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 200
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 429
        assert fake.refresh.call_count == 3

    def test_quota_is_per_user(self, tmp_path, monkeypatch):
        client, _, fake = make_numbers_client(tmp_path, monkeypatch)
        alice = signup(client)
        bob = signup(client, email="bob@example.com")
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(alice)).status_code == 200
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(alice)).status_code == 429
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(bob)).status_code == 200
        assert fake.refresh.call_count == 2

    def test_quota_resets_next_day(self, tmp_path, monkeypatch):
        holder = {"day": "2026-08-31"}
        client, _, fake = make_numbers_client(
            tmp_path, monkeypatch, today=lambda: date.fromisoformat(holder["day"])
        )
        token = signup(client)
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 200
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 429

        holder["day"] = "2026-09-01"
        assert client.post("/api/numbers/TSLA/refresh", headers=auth(token)).status_code == 200

    def test_analysis_endpoint_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = make_numbers_client(tmp_path, monkeypatch)
        assert client.post("/api/numbers/TSLA/refresh").status_code == 401


class TestIngestGating:
    def test_ingest_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.post("/api/ingest/TSLA")
        assert resp.status_code == 401

    def test_ingest_consumes_analysis_quota(self, tmp_path, monkeypatch):
        client, _, _ = make_client(tmp_path, monkeypatch)
        fake = MagicMock(ingest=MagicMock(return_value={"status": "cached", "ticker": "TSLA"}))
        monkeypatch.setattr(main, "_get_ingest_service", lambda: fake)
        token = signup(client)
        assert client.post("/api/ingest/TSLA", headers=auth(token)).status_code == 200
        resp = client.get("/api/auth/quota", headers=auth(token))
        assert resp.json()["analyses"]["used"] == 1

    def test_failed_ingest_refunds_analysis_quota(self, tmp_path, monkeypatch):
        from financial_analyst.ingestion.sec_downloader import TickerNotFoundError

        client, _, _ = make_client(tmp_path, monkeypatch)
        fake = MagicMock(
            ingest=MagicMock(side_effect=TickerNotFoundError("Ticker not found on SEC EDGAR: NOPE"))
        )
        monkeypatch.setattr(main, "_get_ingest_service", lambda: fake)
        token = signup(client)
        for _ in range(2):
            resp = client.post("/api/ingest/NOPE", headers=auth(token))
            assert resp.status_code == 404
        assert client.get("/api/auth/quota", headers=auth(token)).json()["analyses"]["used"] == 0
