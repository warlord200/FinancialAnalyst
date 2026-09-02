"""The numbers backbone: fetch XBRL company-facts and a current price for a
ticker, persist the raw facts and price, and serve computed figures."""

from datetime import datetime, timezone

from financial_analyst.numbers.prices import PriceFetchError
from financial_analyst.numbers.statements import compute
from financial_analyst.storage.json_store import JsonFileStore


class NumbersStore(JsonFileStore):
    def __init__(self, path: str = "./storage/numbers.json") -> None:
        super().__init__(path)

    def set_facts(self, ticker: str, facts: dict) -> dict:
        entry = {
            "facts": facts,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.set(ticker.upper(), entry)
        return entry


class NumbersService:
    def __init__(
        self,
        downloader,
        facts_fetcher,
        price_client,
        store: NumbersStore,
        price_store,
    ) -> None:
        self.downloader = downloader
        self.facts_fetcher = facts_fetcher
        self.price_client = price_client
        self.store = store
        self.price_store = price_store

    def refresh(self, ticker: str) -> dict:
        ticker = ticker.upper()
        self._fetch_and_store_facts(ticker)

        try:
            price = self.price_client.fetch_current(ticker)
            history = self.price_client.fetch_history(ticker)
        except PriceFetchError:
            price = None
            history = []
        if price is not None:
            self.price_store.set_fetched(ticker, price, history)
        return self.get(ticker)

    def resolve(self, ticker: str) -> int:
        """Resolve a ticker to its SEC CIK, raising TickerNotFoundError when
        SEC EDGAR does not know it."""
        return self.downloader.get_cik(ticker.upper())

    def ensure_facts(self, ticker: str, cik: int | None = None) -> dict:
        """Make sure the ticker's XBRL company-facts are cached, fetching
        them when they are not.

        The peer scorecard uses this to pull a peer's numbers into the
        shared store on first use. Unlike :meth:`refresh` it does not touch
        the price layer, so a peer needs no market price to be comparable.
        """
        ticker = ticker.upper()
        if self.store.get(ticker) is None:
            self._fetch_and_store_facts(ticker, cik)
        return self.get(ticker)

    def _fetch_and_store_facts(self, ticker: str, cik: int | None = None) -> None:
        if cik is None:
            cik = self.downloader.get_cik(ticker)
        self.store.set_facts(ticker, self.facts_fetcher(cik))

    def get(self, ticker: str) -> dict | None:
        ticker = ticker.upper()
        entry = self.store.get(ticker)
        if entry is None:
            return None
        return {
            "ticker": ticker,
            "refreshed_at": entry.get("refreshed_at"),
            "financials": compute(entry["facts"]),
            "price": self.price_store.payload(ticker),
        }

    def set_price_override(self, ticker: str, price: float) -> dict:
        self.price_store.set_override(ticker.upper(), price)
        return self.get(ticker.upper())

    def clear_price_override(self, ticker: str) -> dict:
        self.price_store.clear_override(ticker.upper())
        return self.get(ticker.upper())
