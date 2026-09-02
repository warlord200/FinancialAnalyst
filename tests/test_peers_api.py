"""HTTP API tests for the peer scorecard (T10).

The app under test is the real FastAPI app with a faked service boundary:
numbers are served by a NumbersService backed by a per-CIK facts fetcher so
the target (TSLA, FULL_TABLE) and each peer (F, GM) carry genuinely
different XBRL figures, and per-user peer lists live in a temp-dir SQLite
PeerStateStore.

Worked figures come from ``test_steps_peers``: TSLA latest FY2025 revenue
150, gross margin 25%; F latest revenue 300, gross margin 40%; GM latest
revenue 400, net margin 5%.
"""

import pytest

import api.main as main
from financial_analyst.ingestion.sec_downloader import SECDownloadError
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.numbers.xbrl import XBRLEdgarError
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import PeerStateStore, StepStateStore
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import (
    ByCikFactsFetcher,
    F_TABLE,
    FULL_TABLE,
    GM_TABLE,
    FakeDownloader,
    FakePriceClient,
)
from tests.fixtures.xbrl_facts import make_facts

CIKS = {"TSLA": 1318605, "F": 1, "GM": 2}


def default_facts_fetcher():
    return ByCikFactsFetcher(
        {1318605: make_facts(FULL_TABLE), 1: make_facts(F_TABLE), 2: make_facts(GM_TABLE)}
    )


def make_client(
    tmp_path,
    monkeypatch,
    refresh=True,
    email="peers@example.com",
    downloader=None,
    facts_fetcher=None,
):
    numbers = NumbersService(
        downloader=downloader or FakeDownloader(CIKS),
        facts_fetcher=facts_fetcher or default_facts_fetcher(),
        price_client=FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    if refresh:
        numbers.refresh("TSLA")
    db = str(tmp_path / "storage" / "steps.db")
    steps = StepsService(
        numbers_service=numbers,
        state_store=StepStateStore(db),
        peers_store=PeerStateStore(db),
    )
    monkeypatch.setattr(main, "_get_steps_service", lambda: steps)
    monkeypatch.setattr(main, "_get_numbers_service", lambda: numbers)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email=email)
    return client, numbers


def gross_margin_row(scorecard):
    margins = next(t for t in scorecard if t["key"] == "margins")
    return next(r for r in margins["rows"] if r["label"] == "Gross margin")


class TestPeerScorecardApi:
    def test_add_peers_returns_scorecard_with_target_and_peer(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        resp = client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "TSLA"
        assert body["peers"] == ["F"]
        assert [t["key"] for t in body["scorecard"]] == [
            "growth",
            "margins",
            "debt_liquidity",
            "returns",
        ]
        growth = body["scorecard"][0]
        assert growth["columns"] == ["TSLA", "F"]
        assert growth["column_labels"] == {"TSLA": "TSLA · FY2025", "F": "F · FY2025"}
        cagr = next(r for r in growth["rows"] if r["label"] == "Revenue CAGR (5y)")
        assert cagr["values"]["TSLA"] == pytest.approx((150 / 100) ** (1 / 5) - 1)
        assert cagr["values"]["F"] == pytest.approx((300 / 100) ** (1 / 5) - 1)
        row = gross_margin_row(body["scorecard"])
        assert row["values"]["TSLA"] == pytest.approx(0.25)
        assert row["values"]["F"] == pytest.approx(0.40)
        assert {"type": "xbrl_fact", "value": "GrossProfit"} in row["sources"]

    def test_get_peers_returns_saved_list_and_scorecard(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        client.put("/api/steps/TSLA/peers", json={"peers": ["F", "GM"]})
        resp = client.get("/api/steps/TSLA/peers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["peers"] == ["F", "GM"]
        assert body["scorecard"][0]["columns"] == ["TSLA", "F", "GM"]
        row = gross_margin_row(body["scorecard"])
        assert row["values"]["F"] == pytest.approx(0.40)
        assert row["values"]["GM"] == pytest.approx(0.30)

    def test_set_peers_replaces_the_list(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        client.put("/api/steps/TSLA/peers", json={"peers": ["GM"]})
        body = client.get("/api/steps/TSLA/peers").json()
        assert body["peers"] == ["GM"]
        assert body["scorecard"][0]["columns"] == ["TSLA", "GM"]

    def test_set_peers_drops_duplicates_and_the_target_itself(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        resp = client.put(
            "/api/steps/TSLA/peers", json={"peers": ["f", "F", "TSLA", "GM"]}
        )
        assert resp.status_code == 200
        assert resp.json()["peers"] == ["F", "GM"]

    def test_delete_clears_peers(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        resp = client.delete("/api/steps/TSLA/peers")
        assert resp.status_code == 200
        assert resp.json()["peers"] == []
        assert resp.json()["scorecard"] == []

    def test_add_unknown_peer_returns_404_and_leaves_list_unchanged(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        resp = client.put("/api/steps/TSLA/peers", json={"peers": ["NOPE"]})
        assert resp.status_code == 404
        body = client.get("/api/steps/TSLA/peers").json()
        assert body["peers"] == ["F"]

    def test_add_peers_requires_target_numbers(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch, refresh=False)
        resp = client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert resp.status_code == 404

    def test_get_peers_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/peers").status_code == 401

    def test_peer_lists_are_isolated_between_users(self, tmp_path, monkeypatch):
        client_a, _ = make_client(tmp_path, monkeypatch, email="a@example.com")
        client_a.put("/api/steps/TSLA/peers", json={"peers": ["F"]})

        client_b, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
        signup_and_auth(client_b, email="b@example.com")
        body = client_b.get("/api/steps/TSLA/peers").json()
        assert body["peers"] == []
        assert body["scorecard"] == []

    def test_peer_facts_are_pulled_once_into_the_shared_numbers_store(self, tmp_path, monkeypatch):
        client, numbers = make_client(tmp_path, monkeypatch)
        assert numbers.store.get("F") is None

        first = client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert first.json()["fetched"] == ["F"]
        assert numbers.store.get("F") is not None
        fetches_after_first = numbers.facts_fetcher.calls.count(1)

        second = client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert second.json()["fetched"] == []
        assert numbers.facts_fetcher.calls.count(1) == fetches_after_first

    def test_put_consumes_an_analysis_only_when_a_peer_is_fetched(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch)
        baseline = client.get("/api/auth/quota").json()["analyses"]["used"]

        client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        after_fetch = client.get("/api/auth/quota").json()["analyses"]["used"]
        assert after_fetch == baseline + 1

        client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        after_cached = client.get("/api/auth/quota").json()["analyses"]["used"]
        assert after_cached == baseline + 1

        bad = client.put("/api/steps/TSLA/peers", json={"peers": ["NOPE"]})
        assert bad.status_code == 404
        after_bad = client.get("/api/auth/quota").json()["analyses"]["used"]
        assert after_bad == baseline + 1


class OutageFactsFetcher:
    """Serves the target's facts but EDGAR is down for every other CIK."""

    def __init__(self):
        self.calls = []

    def __call__(self, cik):
        self.calls.append(cik)
        if cik == 1318605:
            return make_facts(FULL_TABLE)
        raise XBRLEdgarError("EDGAR company-facts down")


class OutageDownloader(FakeDownloader):
    """Resolves the target but SEC EDGAR is down for every other ticker."""

    def get_cik(self, ticker):
        if ticker.upper() == "TSLA":
            return 1318605
        raise SECDownloadError("EDGAR submissions down")


class TestPeerOutageHandling:
    def test_peer_pull_503_and_refunds_quota_when_xbrl_fetch_fails(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch, facts_fetcher=OutageFactsFetcher())
        baseline = client.get("/api/auth/quota").json()["analyses"]["used"]

        resp = client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert resp.status_code == 503
        assert client.get("/api/auth/quota").json()["analyses"]["used"] == baseline

    def test_peer_pull_503_and_refunds_quota_when_ticker_lookup_fails(self, tmp_path, monkeypatch):
        client, _ = make_client(
            tmp_path, monkeypatch, downloader=OutageDownloader({})
        )
        baseline = client.get("/api/auth/quota").json()["analyses"]["used"]

        resp = client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert resp.status_code == 503
        assert client.get("/api/auth/quota").json()["analyses"]["used"] == baseline

    def test_delete_clears_peers_even_without_target_numbers(self, tmp_path, monkeypatch):
        client, _ = make_client(tmp_path, monkeypatch, refresh=False)
        resp = client.delete("/api/steps/TSLA/peers")
        assert resp.status_code == 200
        assert resp.json() == {"ticker": "TSLA", "peers": [], "scorecard": []}
