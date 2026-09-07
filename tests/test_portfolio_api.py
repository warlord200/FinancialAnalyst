"""HTTP API tests for the dossier Portfolio and Library (T13).

The app under test is the real FastAPI app with a faked service boundary:
numbers come from a NumbersService backed by per-CIK facts and a price
client, the ingest registry is a temp-dir CacheRegistry seeded directly
(the ingest pipeline is out of scope here), and per-user gates, done-marks
and saved-tickers live in temp-dir SQLite stores.

The portfolio endpoint is the per-user dashboard read: one row per
ingested ticker carrying the user's gate status, done-marks for steps 2-4,
the saved flag, and whether the numbers layer is ready. The library
endpoints save/unsave tickers per user.
"""

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.library import LibraryStore
from financial_analyst.steps.portfolio import PortfolioService
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import StepStateStore
from financial_analyst.storage.registry import CacheRegistry
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import (
    FULL_TABLE,
    FakeDownloader,
    FakeFactsFetcher,
    FakePriceClient,
)
from tests.fixtures.xbrl_facts import make_facts

CIKS = {"TSLA": 1318605, "AAPL": 1}
INGESTED_AT = "2026-09-01T00:00:00+00:00"


def _numbers(tmp_path):
    return NumbersService(
        downloader=FakeDownloader(CIKS),
        facts_fetcher=FakeFactsFetcher(make_facts(FULL_TABLE)),
        price_client=FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )


def _registry(tmp_path, tickers=("TSLA", "AAPL")):
    registry = CacheRegistry(str(tmp_path / "storage" / "ingest_registry.json"))
    for ticker in tickers:
        registry.add(ticker, {"ingested_at": INGESTED_AT})
    return registry


def make_client(tmp_path, monkeypatch, email="alice@example.com", seed=("TSLA", "AAPL")):
    numbers = _numbers(tmp_path)
    numbers.refresh("TSLA")
    db = str(tmp_path / "storage" / "steps.db")
    state = StepStateStore(db)
    registry = _registry(tmp_path, seed)
    steps = StepsService(numbers_service=numbers, state_store=state)
    portfolio = PortfolioService(
        registry=registry,
        numbers_store=numbers.store,
        state_store=state,
        library_store=LibraryStore(db),
    )
    monkeypatch.setattr(main, "_get_steps_service", lambda: steps)
    monkeypatch.setattr(main, "_get_numbers_service", lambda: numbers)
    monkeypatch.setattr(main, "_get_portfolio_service", lambda: portfolio)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email=email)
    return client, steps, numbers, registry


def bob_client(tmp_path, monkeypatch, email="bob@example.com"):
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email=email)
    return client


class TestPortfolioApi:
    def test_portfolio_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/portfolio").status_code == 401

    def test_portfolio_is_empty_when_nothing_ingested(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch, seed=())
        assert client.get("/api/portfolio").json() == []

    def test_portfolio_lists_every_ingested_ticker(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        body = client.get("/api/portfolio").json()
        assert {row["ticker"] for row in body} == {"AAPL", "TSLA"}
        assert all(row["ingested_at"] == INGESTED_AT for row in body)

    def test_portfolio_defaults_when_user_has_no_state(self, tmp_path, monkeypatch):
        """A fresh user sees every ingested ticker with pending/false state."""
        client, _, numbers, _ = make_client(tmp_path, monkeypatch, email="new@example.com")
        numbers.refresh("AAPL")
        body = client.get("/api/portfolio").json()
        for row in body:
            assert row["gate"] == {"status": "pending"}
            assert row["done"] == {"2": False, "3": False, "4": False}
            assert row["saved"] is False

    def test_portfolio_reports_numbers_ready(self, tmp_path, monkeypatch):
        client, _, numbers, _ = make_client(tmp_path, monkeypatch)
        numbers.refresh("AAPL")
        by_ticker = {row["ticker"]: row for row in client.get("/api/portfolio").json()}
        assert by_ticker["TSLA"]["numbers_ready"] is True
        assert by_ticker["AAPL"]["numbers_ready"] is True

    def test_portfolio_marks_numbers_not_ready_when_unrefreshed(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch, seed=("AAPL",))
        body = client.get("/api/portfolio").json()
        assert body[0]["ticker"] == "AAPL"
        assert body[0]["numbers_ready"] is False

    def test_portfolio_reflects_gate_and_done_and_saved_state(self, tmp_path, monkeypatch):
        client, _, numbers, _ = make_client(tmp_path, monkeypatch)
        numbers.refresh("AAPL")
        client.post("/api/steps/TSLA/gate", json={"decision": "accept"})
        client.post("/api/steps/TSLA/done/2")
        client.post("/api/steps/TSLA/done/3")
        client.post("/api/library/TSLA")
        by_ticker = {row["ticker"]: row for row in client.get("/api/portfolio").json()}
        tsla = by_ticker["TSLA"]
        assert tsla["gate"] == {"status": "accepted"}
        assert tsla["done"] == {"2": True, "3": True, "4": False}
        assert tsla["saved"] is True
        aapl = by_ticker["AAPL"]
        assert aapl["gate"] == {"status": "pending"}
        assert aapl["saved"] is False

    def test_portfolio_shows_rejected_gate(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        client.post("/api/steps/TSLA/gate", json={"decision": "reject"})
        by_ticker = {row["ticker"]: row for row in client.get("/api/portfolio").json()}
        assert by_ticker["TSLA"]["gate"] == {"status": "rejected"}

    def test_portfolio_state_is_per_user(self, tmp_path, monkeypatch):
        client, _, numbers, _ = make_client(tmp_path, monkeypatch)
        numbers.refresh("AAPL")
        client.post("/api/steps/TSLA/gate", json={"decision": "accept"})
        client.post("/api/library/TSLA")

        bob = bob_client(tmp_path, monkeypatch)
        by_ticker = {row["ticker"]: row for row in bob.get("/api/portfolio").json()}
        assert by_ticker["TSLA"]["gate"] == {"status": "pending"}
        assert by_ticker["TSLA"]["saved"] is False


class TestLibraryApi:
    def test_library_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/library").status_code == 401
        assert client.post("/api/library/TSLA").status_code == 401
        assert client.delete("/api/library/TSLA").status_code == 401

    def test_library_is_empty_before_any_save(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        assert client.get("/api/library").json() == []

    def test_save_lists_the_ticker_in_the_library(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.post("/api/library/TSLA")
        assert resp.status_code == 200
        assert resp.json()["saved"] is True
        body = client.get("/api/library").json()
        assert [row["ticker"] for row in body] == ["TSLA"]
        assert body[0]["saved_at"]

    def test_saving_twice_is_idempotent(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        first = client.post("/api/library/TSLA").json()
        second = client.post("/api/library/TSLA").json()
        assert second["saved"] is True
        assert second["saved_at"] == first["saved_at"]
        body = client.get("/api/library").json()
        assert len(body) == 1
        assert body[0]["ticker"] == "TSLA"

    def test_library_lists_only_saved_tickers(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        client.post("/api/library/TSLA")
        body = client.get("/api/library").json()
        assert [row["ticker"] for row in body] == ["TSLA"]

    def test_unsave_removes_the_ticker(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        client.post("/api/library/TSLA")
        resp = client.delete("/api/library/TSLA")
        assert resp.status_code == 200
        assert resp.json()["saved"] is False
        assert client.get("/api/library").json() == []

    def test_unsave_of_an_unsaved_ticker_is_idempotent(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        resp = client.delete("/api/library/TSLA")
        assert resp.status_code == 200
        assert resp.json()["saved"] is False

    def test_library_is_per_user(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        client.post("/api/library/TSLA")

        bob = bob_client(tmp_path, monkeypatch)
        assert bob.get("/api/library").json() == []

    def test_unsave_only_affects_the_calling_user(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        client.post("/api/library/TSLA")

        bob = bob_client(tmp_path, monkeypatch)
        bob.delete("/api/library/TSLA")
        body = client.get("/api/library").json()
        assert [row["ticker"] for row in body] == ["TSLA"]

    def test_save_unknown_ticker_returns_404(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        assert client.post("/api/library/ZZZZ").status_code == 404

    def test_unsave_unknown_ticker_returns_404(self, tmp_path, monkeypatch):
        client, _, _, _ = make_client(tmp_path, monkeypatch)
        assert client.delete("/api/library/ZZZZ").status_code == 404
