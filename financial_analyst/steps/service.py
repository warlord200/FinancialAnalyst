"""The dossier step service: reads the shared numbers layer and the
per-user step state, and composes step responses."""

from financial_analyst.steps import STEP_ONE
from financial_analyst.steps.one_pager import build_one_pager


class StepsService:
    def __init__(self, numbers_service, state_store) -> None:
        self.numbers = numbers_service
        self.state = state_store

    def one_pager(self, email: str, ticker: str) -> dict | None:
        ticker = ticker.upper()
        numbers = self.numbers.get(ticker)
        if numbers is None:
            return None
        return {
            "ticker": ticker,
            "one_pager": build_one_pager(numbers["financials"]),
            "gate": self.state.get_gate(email, ticker, STEP_ONE),
        }

    def set_gate(self, email: str, ticker: str, step: int, decision: str) -> dict | None:
        """Record a step decision. Returns None when the ticker has no
        numbers, so the caller can 404. Accepting a step is the seam where
        the step 2-4 drafts will be kicked off once those exist (T5+)."""
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        status = "accepted" if decision == "accept" else "rejected"
        gate = self.state.set_gate(email, ticker, step, status)
        return {"ticker": ticker, "gate": gate}
