"""Per-user portfolio and library reads over the shared content layer.

The portfolio is the user's dashboard: every ingested ticker with the
calling user's dossier state (gate status, done-marks for steps 2-4, saved
flag) and whether the shared numbers layer is ready for it. The library is
the user-level collection of saved tickers.

The tickers and the numbers layer are shared; the state they are annotated
with is private per user (gates, done-marks) and per-user saved (library).
Portfolio reads load the user's whole state in a handful of queries, never
one per ingested ticker.
"""

from financial_analyst.steps import STEP_ONE

DONE_STEPS = (2, 3, 4)


class PortfolioService:
    def __init__(
        self,
        registry,
        numbers_store,
        state_store,
        library_store,
    ) -> None:
        self.registry = registry
        self.numbers_store = numbers_store
        self.state = state_store
        self.library_store = library_store

    def portfolio(self, email: str) -> list[dict]:
        """One row per ingested ticker with the user's dossier state.

        The ingested tickers come from the shared ingest registry; gates,
        done-marks and the saved set are loaded for the whole user up
        front, and numbers readiness is a membership check on the shared
        numbers store. Safe when the user has no state at all: every row
        then shows a pending gate, no done-marks, and not saved.
        """
        gates = self.state.all_gates(email)
        done = self.state.all_done(email)
        saved = {row["ticker"] for row in self.library_store.saved_tickers(email)}
        numbers = set(self.numbers_store.all().keys()) if self.numbers_store else set()

        rows = []
        for entry in self.registry.list_all():
            ticker = entry["ticker"]
            gate_status = gates.get((ticker, STEP_ONE), "pending")
            done_marks = done.get(ticker, set())
            rows.append(
                {
                    "ticker": ticker,
                    "ingested_at": entry.get("ingested_at"),
                    "numbers_ready": ticker in numbers,
                    "gate": {"status": gate_status},
                    "done": {
                        str(step): step in done_marks for step in DONE_STEPS
                    },
                    "saved": ticker in saved,
                }
            )
        return rows

    def save_to_library(self, email: str, ticker: str) -> dict | None:
        """Save an ingested ticker to the user's library.

        Returns None when the ticker is not ingested, so the caller can
        404. Saving a ticker that is already saved keeps its original save
        time (idempotent).
        """
        ticker = ticker.upper()
        if self.registry.get(ticker) is None:
            return None
        row = self.library_store.save(email, ticker)
        return {"ticker": ticker, "saved": True, "saved_at": row["saved_at"]}

    def unsave(self, email: str, ticker: str) -> dict | None:
        """Remove a ticker from the user's library.

        Returns None when the ticker is not ingested, so the caller can
        404. Un-saving a ticker that is not saved is a no-op that still
        reports not saved.
        """
        ticker = ticker.upper()
        if self.registry.get(ticker) is None:
            return None
        self.library_store.unsave(email, ticker)
        return {"ticker": ticker, "saved": False}

    def library(self, email: str) -> list[dict]:
        """The tickers the user has saved, newest save first."""
        return self.library_store.saved_tickers(email)
