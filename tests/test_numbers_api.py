import pytest

import api.main as main
from financial_analyst.ingestion.sec_downloader import TickerNotFoundError
from financial_analyst.numbers.prices import PriceFetchError, PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.numbers.statements import compute
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import (
    FULL_TABLE,
    FakeDownloader,
    FakeFactsFetcher,
    FakePriceClient,
)
from tests.fixtures.xbrl_facts import make_facts


def make_client(tmp_path, monkeypatch, ciks=None, facts=None, price_client=None):
    service = NumbersService(
        downloader=FakeDownloader(ciks or {"TSLA": 1318605}),
        facts_fetcher=FakeFactsFetcher(facts or make_facts(FULL_TABLE)),
        price_client=price_client or FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    monkeypatch.setattr(main, "_get_numbers_service", lambda: service)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email="numbers@example.com")
    return client, service


def test_refresh_returns_financials_and_price(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    resp = client.post("/api/numbers/TSLA/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "TSLA"
    assert body["financials"]["fiscal_years"] == [2025, 2024, 2023, 2022, 2021, 2020]
    assert body["financials"]["income_statement"]["revenue"]["2025"] == 150.0
    assert body["financials"]["ratios"]["gross_margin"]["2025"] == pytest.approx(0.25)
    assert body["price"]["effective"]["price"] == 253.4
    assert body["price"]["effective"]["source"] == "yahoo"


def test_refresh_unknown_ticker_returns_404(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, ciks={})
    resp = client.post("/api/numbers/NOPE/refresh")
    assert resp.status_code == 404


def test_get_before_refresh_returns_404(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    resp = client.get("/api/numbers/TSLA")
    assert resp.status_code == 404


def test_get_after_refresh_is_cached_and_reproducible(tmp_path, monkeypatch):
    client, service = make_client(tmp_path, monkeypatch)
    client.post("/api/numbers/TSLA/refresh")
    fetched_before = service.facts_fetcher.calls

    resp = client.get("/api/numbers/TSLA")
    assert resp.status_code == 200
    body = resp.json()
    assert service.facts_fetcher.calls == fetched_before

    stored = service.store.get("TSLA")
    assert compute(stored["facts"]) == body["financials"]


def test_price_override_changes_stored_price(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    client.post("/api/numbers/TSLA/refresh")

    resp = client.put("/api/numbers/TSLA/price", json={"price": 260.0})
    assert resp.status_code == 200
    assert resp.json()["price"]["effective"]["price"] == 260.0
    assert resp.json()["price"]["effective"]["source"] == "override"

    body = client.get("/api/numbers/TSLA").json()
    assert body["price"]["effective"]["price"] == 260.0
    assert body["price"]["override"]["price"] == 260.0


def test_clear_price_override(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    client.post("/api/numbers/TSLA/refresh")
    client.put("/api/numbers/TSLA/price", json={"price": 260.0})

    resp = client.delete("/api/numbers/TSLA/price")
    assert resp.status_code == 200
    body = resp.json()
    assert body["price"]["effective"]["price"] == 253.4
    assert body["price"]["effective"]["source"] == "yahoo"
    assert body["price"]["override"] is None


def test_refresh_price_failure_still_returns_financials(tmp_path, monkeypatch):
    failing = FakePriceClient(error=PriceFetchError("down"))
    client, _ = make_client(tmp_path, monkeypatch, price_client=failing)
    resp = client.post("/api/numbers/TSLA/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["financials"]["income_statement"]["revenue"]["2025"] == 150.0
    assert body["price"] is None
