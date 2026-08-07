import json
import threading
from pathlib import Path


class CacheRegistry:
    def __init__(self, path: str = "./storage/registry.json") -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.path.is_file():
            with open(self.path, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp.replace(self.path)

    def get(self, ticker: str) -> dict | None:
        with self._lock:
            return self._data.get(ticker.upper())

    def add(self, ticker: str, entry: dict) -> None:
        with self._lock:
            self._data[ticker.upper()] = entry
            self._save()

    def clear(self, ticker: str) -> None:
        with self._lock:
            self._data.pop(ticker.upper(), None)
            self._save()

    def list_all(self) -> list[dict]:
        with self._lock:
            entries = [{**entry, "ticker": ticker} for ticker, entry in self._data.items()]
        entries.sort(key=lambda e: e.get("report_generated_at", ""), reverse=True)
        return entries
