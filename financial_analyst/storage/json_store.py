import json
import threading
from pathlib import Path


class JsonFileStore:
    def __init__(self, path: str) -> None:
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

    def get(self, key: str) -> dict | None:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    def remove(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._save()

    def all(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._data)
