"""Current price and price history from a free source (Yahoo Finance's
unofficial chart API), plus a persisted manual override."""

from datetime import datetime, timezone
from typing import Optional

from financial_analyst.net import DEFAULT_USER_AGENT, ExternalSourceError, get_with_retry
from financial_analyst.storage.json_store import JsonFileStore

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HISTORY_RANGE = "5y"

USER_AGENT = "Mozilla/5.0 " + DEFAULT_USER_AGENT


class PriceFetchError(Exception):
    pass


class YahooFinancePriceClient:
    def _chart(self, ticker: str, params: dict) -> dict:
        try:
            resp = get_with_retry(
                YAHOO_CHART_URL.format(symbol=ticker.upper()),
                params=params,
                user_agent=USER_AGENT,
            )
            payload = resp.json()
        except ExternalSourceError as exc:
            raise PriceFetchError(f"Price fetch failed for {ticker}: {exc}")
        results = payload.get("chart", {}).get("result")
        if not results:
            raise PriceFetchError(f"No price data returned for {ticker}")
        return results[0]

    def fetch_current(self, ticker: str) -> float:
        result = self._chart(ticker, {"range": "1d", "interval": "1d"})
        price = result.get("meta", {}).get("regularMarketPrice")
        if price is None:
            raise PriceFetchError(f"No current price returned for {ticker}")
        return float(price)

    def fetch_history(self, ticker: str) -> list[dict]:
        result = self._chart(
            ticker, {"range": HISTORY_RANGE, "interval": "1d"}
        )
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        history = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            history.append({"date": date, "close": float(close)})
        history.sort(key=lambda row: row["date"])
        return history


class PriceStore(JsonFileStore):
    def __init__(self, path: str = "./storage/prices.json") -> None:
        super().__init__(path)

    def effective_price(self, ticker: str) -> Optional[dict]:
        entry = self.get(ticker.upper())
        if entry is None:
            return None
        if entry.get("override"):
            return {
                "price": entry["override"]["price"],
                "source": "override",
                "as_of": entry["override"]["set_at"],
            }
        return {
            "price": entry["fetched_price"],
            "source": "yahoo",
            "as_of": entry.get("fetched_at"),
        }

    def set_fetched(self, ticker: str, price: float, history: list[dict]) -> None:
        existing = self.get(ticker.upper()) or {}
        self.set(
            ticker.upper(),
            {
                "fetched_price": price,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "history": history,
                "override": existing.get("override"),
            },
        )

    def set_override(self, ticker: str, price: float) -> None:
        entry = self.get(ticker.upper()) or {}
        entry["override"] = {
            "price": float(price),
            "set_at": datetime.now(timezone.utc).isoformat(),
        }
        self.set(ticker.upper(), entry)

    def clear_override(self, ticker: str) -> None:
        entry = self.get(ticker.upper())
        if entry and entry.get("override"):
            entry["override"] = None
            self.set(ticker.upper(), entry)

    def payload(self, ticker: str) -> Optional[dict]:
        entry = self.get(ticker.upper())
        if entry is None:
            return None
        return {
            "effective": self.effective_price(ticker.upper()),
            "fetched": {
                "price": entry.get("fetched_price"),
                "as_of": entry.get("fetched_at"),
            },
            "override": entry.get("override"),
            "history": entry.get("history", []),
        }
