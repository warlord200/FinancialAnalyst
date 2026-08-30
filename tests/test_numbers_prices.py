import requests
import pytest

from financial_analyst.numbers.prices import PriceFetchError, PriceStore, YahooFinancePriceClient

CURRENT_JSON = {
    "chart": {
        "result": [
            {
                "meta": {"regularMarketPrice": 253.4},
                "timestamp": [1787923800],
                "indicators": {"quote": [{"close": [253.4]}]},
            }
        ]
    }
}

HISTORY_JSON = {
    "chart": {
        "result": [
            {
                "timestamp": [1735421400, 1766957400, 1787923800],
                "indicators": {
                    "quote": [{"close": [201.0, 241.5, None]}]
                },
            }
        ]
    }
}

EMPTY_JSON = {"chart": {"result": [{"meta": {}}]}}


@pytest.fixture
def fake_get(monkeypatch):
    responses = {}

    def set_response(symbol, payload):
        responses[symbol] = payload

    def fake_requests_get(url, params=None, headers=None, timeout=None):
        symbol = url.rsplit("/", 1)[-1].upper()
        if symbol not in responses:
            raise AssertionError(f"Unexpected URL: {url}?{params}")
        return FakeResponse(responses[symbol])

    monkeypatch.setattr("requests.get", fake_requests_get)
    return set_response


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def test_yahoo_parses_current_price(fake_get):
    fake_get("TSLA", CURRENT_JSON)
    client = YahooFinancePriceClient()
    assert client.fetch_current("TSLA") == pytest.approx(253.4)


def test_yahoo_parses_history_oldest_first_dropping_none(fake_get):
    fake_get("TSLA", HISTORY_JSON)
    client = YahooFinancePriceClient()
    history = client.fetch_history("TSLA")
    assert history == [
        {"date": "2024-12-28", "close": 201.0},
        {"date": "2025-12-28", "close": 241.5},
    ]


def test_yahoo_raises_when_price_missing(fake_get):
    fake_get("NOPE", EMPTY_JSON)
    client = YahooFinancePriceClient()
    with pytest.raises(PriceFetchError):
        client.fetch_current("NOPE")


def test_yahoo_translates_network_errors_to_price_fetch_error(monkeypatch):
    def boom(url, params=None, headers=None, timeout=None):
        raise requests.ConnectionError("down")

    monkeypatch.setattr("requests.get", boom)
    client = YahooFinancePriceClient()
    with pytest.raises(PriceFetchError):
        client.fetch_current("TSLA")


def test_price_store_override_changes_effective_price(tmp_path):
    store = PriceStore(str(tmp_path / "prices.json"))
    store.set(
        "TSLA",
        {
            "fetched_price": 253.4,
            "fetched_at": "2026-08-29T16:00:00Z",
            "override": None,
            "history": [{"date": "2026-08-29", "close": 253.4}],
        },
    )
    assert store.effective_price("TSLA")["price"] == 253.4
    assert store.effective_price("TSLA")["source"] == "yahoo"

    store.set_override("TSLA", 260.0)
    assert store.effective_price("TSLA")["price"] == 260.0
    assert store.effective_price("TSLA")["source"] == "override"

    store.clear_override("TSLA")
    assert store.effective_price("TSLA")["source"] == "yahoo"


def test_price_store_effective_none_when_absent(tmp_path):
    store = PriceStore(str(tmp_path / "prices.json"))
    assert store.effective_price("TSLA") is None
