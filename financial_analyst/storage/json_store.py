import json
import threading
from pathlib import Path


class JsonFileStore:
    """A JSON file read and written in place.

    In worker deployments the background process writes files (e.g.
    ``ingest_registry.json``) that the API process reads, so reads and
    writes reload from disk whenever the file's signature (mtime, size)
    changed since the last load or save.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._signature: tuple[int, int] | None = None
        self._load()

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
            return stat.st_mtime_ns, stat.st_size
        except FileNotFoundError:
            return None

    def _read(self) -> dict[str, dict]:
        if self.path.is_file():
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load(self) -> None:
        self._data = self._read()
        self._signature = self._file_signature(self.path)

    def _reload_if_changed(self) -> None:
        signature = self._file_signature(self.path)
        if signature != self._signature:
            self._data = self._read()
            self._signature = signature

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp.replace(self.path)
        self._signature = self._file_signature(self.path)

    def get(self, key: str) -> dict | None:
        with self._lock:
            self._reload_if_changed()
            return self._data.get(key)

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._reload_if_changed()
            self._data[key] = value
            self._save()

    def remove(self, key: str) -> None:
        with self._lock:
            self._reload_if_changed()
            self._data.pop(key, None)
            self._save()

    def all(self) -> dict[str, dict]:
        with self._lock:
            self._reload_if_changed()
            return dict(self._data)
