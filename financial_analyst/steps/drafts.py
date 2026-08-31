"""Persisted, shared drafts for the dossier steps.

Drafts are derived from the shared content corpus, so today a draft is the
same for every user and can be cached in the shared JSON store. Per-user
inputs (uploads) that influence steps 2 and 4 will make drafts per-user
when they land; the cache stays the shared fast path until then.
"""

from financial_analyst.storage.json_store import JsonFileStore


class DraftStore(JsonFileStore):
    def __init__(self, path: str = "./storage/drafts.json") -> None:
        super().__init__(path)

    def get_draft(self, ticker: str, artifact_type: str) -> dict | None:
        entry = self.get(ticker.upper())
        if entry is None:
            return None
        return entry.get(artifact_type)

    def set_draft(self, ticker: str, artifact_type: str, artifact: dict) -> None:
        entry = self.get(ticker.upper()) or {}
        entry[artifact_type] = artifact
        self.set(ticker.upper(), entry)
