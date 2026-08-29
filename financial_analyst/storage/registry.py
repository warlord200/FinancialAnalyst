from financial_analyst.storage.json_store import JsonFileStore


class CacheRegistry(JsonFileStore):
    def __init__(self, path: str = "./storage/registry.json") -> None:
        super().__init__(path)

    def get(self, ticker: str) -> dict | None:
        return super().get(ticker.upper())

    def add(self, ticker: str, entry: dict) -> None:
        self.set(ticker.upper(), entry)

    def clear(self, ticker: str) -> None:
        self.remove(ticker.upper())

    def list_all(self) -> list[dict]:
        entries = [
            {**entry, "ticker": ticker} for ticker, entry in self.all().items()
        ]
        entries.sort(key=lambda e: e.get("report_generated_at", ""), reverse=True)
        return entries
