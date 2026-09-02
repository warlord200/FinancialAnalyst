"""The dossier step service: reads the shared numbers layer, the shared
content corpus, and the per-user step state, and composes step responses.

Step 1 (the one-pager) is a pure derivation from the numbers layer.
Steps 2+ are source-tagged artifacts produced by the generation framework
over the shared corpus; they are cached per ticker so a repeat view is
instant and stable.
"""

from financial_analyst.steps import STEP_ONE
from financial_analyst.steps.business_swot import ARTIFACT_TYPE, build_business_swot
from financial_analyst.steps.financials import ARTIFACT_TYPE as FINANCIALS_TYPE
from financial_analyst.steps.financials import build_financials
from financial_analyst.steps.generation import NoSourceError
from financial_analyst.steps.one_pager import build_one_pager
from financial_analyst.steps.peers import build_scorecard
from financial_analyst.steps.strategy import ARTIFACT_TYPE as STRATEGY_TYPE
from financial_analyst.steps.strategy import build_strategy


class StepsService:
    def __init__(
        self,
        numbers_service,
        state_store,
        generator=None,
        draft_store=None,
        chat_service=None,
        peers_store=None,
    ) -> None:
        self.numbers = numbers_service
        self.state = state_store
        self.generator = generator
        self.drafts = draft_store
        self.chat_service = chat_service
        self.peers_store = peers_store

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
        the step 2-4 drafts are kicked off once the eager-drafting pipeline
        lands; for now drafts are generated on demand and cached."""
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        status = "accepted" if decision == "accept" else "rejected"
        gate = self.state.set_gate(email, ticker, step, status)
        return {"ticker": ticker, "gate": gate}

    def business_swot(self, email: str, ticker: str) -> dict | None:
        """Generate (or serve from cache) the Step 2 Business & SWOT draft.

        Returns None when the ticker has no indexed corpus, so the caller
        can 404. The email is unused for now because the draft is shared.
        """
        ticker = ticker.upper()
        cached = self.drafts.get_draft(ticker, ARTIFACT_TYPE) if self.drafts else None
        if cached is not None:
            return {"ticker": ticker, "artifact": cached, "cached": True}
        if self.generator is None:
            return None
        try:
            artifact = build_business_swot(self.generator, ticker)
        except NoSourceError:
            return None
        if self.drafts is not None:
            self.drafts.set_draft(ticker, ARTIFACT_TYPE, artifact.model_dump())
        return {"ticker": ticker, "artifact": artifact, "cached": False}

    def financials(self, email: str, ticker: str) -> dict | None:
        """Generate (or serve from cache) the Step 3 Financials artifact.

        Returns None when the ticker has no numbers or no indexed corpus, so
        the caller can 404. The tables come from the numbers layer; the
        forensic note is drafted over Item 7/8. The email is unused for now
        because the draft is shared.
        """
        ticker = ticker.upper()
        cached = self.drafts.get_draft(ticker, FINANCIALS_TYPE) if self.drafts else None
        if cached is not None:
            return {"ticker": ticker, "artifact": cached, "cached": True}
        numbers = self.numbers.get(ticker)
        if numbers is None or self.generator is None:
            return None
        try:
            artifact = build_financials(self.generator, ticker, numbers["financials"])
        except NoSourceError:
            return None
        if self.drafts is not None:
            self.drafts.set_draft(ticker, FINANCIALS_TYPE, artifact.model_dump())
        return {"ticker": ticker, "artifact": artifact, "cached": False}

    def strategy(self, email: str, ticker: str) -> dict | None:
        """Generate (or serve from cache) the Step 4 Strategy artifact.

        Returns None when the ticker has no numbers or no indexed corpus, so
        the caller can 404. The plan, capex, and financing sections are
        drafted over Item 5/7; the long-run returns table comes from the
        numbers layer. The email is unused for now because the draft is
        shared.
        """
        ticker = ticker.upper()
        cached = self.drafts.get_draft(ticker, STRATEGY_TYPE) if self.drafts else None
        if cached is not None:
            return {"ticker": ticker, "artifact": cached, "cached": True}
        numbers = self.numbers.get(ticker)
        if numbers is None or self.generator is None:
            return None
        try:
            artifact = build_strategy(self.generator, ticker, numbers["financials"])
        except NoSourceError:
            return None
        if self.drafts is not None:
            self.drafts.set_draft(ticker, STRATEGY_TYPE, artifact.model_dump())
        return {"ticker": ticker, "artifact": artifact, "cached": False}

    def chat(
        self,
        email: str,
        ticker: str,
        step: int,
        question: str,
        search_all: bool = False,
    ) -> dict | None:
        """Answer a question scoped to the step's source items by default,
        or to the whole corpus via the search-everything escape hatch.

        Returns None when no chat service is wired, so the caller can 404.
        The email is unused for now because chat history is not persisted;
        per-user chat state lands with the thesis work.
        """
        ticker = ticker.upper()
        if self.chat_service is None:
            return None
        return self.chat_service.answer(ticker, question, step, search_all)

    def peers(self, email: str, ticker: str) -> dict | None:
        """Return the user's peer list for a company plus the scorecard
        comparing the target against those peers' latest XBRL figures.

        Returns None when the target has no numbers (nothing to compare), so
        the caller can 404. The peer list itself is private per user; the
        numbers they are compared against are the shared numbers layer.
        """
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        peers = self.peers_store.list_peers(email, ticker) if self.peers_store else []
        return self._peer_view(ticker, peers)

    def set_peers(self, email: str, ticker: str, peers: list[str]) -> dict | None:
        """Set the user's peer list for a company.

        Every peer ticker is validated against SEC EDGAR before anything is
        fetched, and any peer whose XBRL facts are not yet in the shared
        numbers store is pulled in on first use. Returns None when the
        target has no numbers. The returned dict carries ``fetched`` — the
        peer tickers whose facts were pulled — so callers can decide whether
        the request consumed quota.
        """
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        cleaned: list[str] = []
        for peer in (str(p).strip().upper() for p in (peers or [])):
            if peer and peer != ticker and peer not in cleaned:
                cleaned.append(peer)
        new = [peer for peer in cleaned if self.numbers.get(peer) is None]
        ciks = {peer: self.numbers.resolve(peer) for peer in new}
        for peer in new:
            self.numbers.ensure_facts(peer, ciks[peer])
        if self.peers_store is not None:
            self.peers_store.set_peers(email, ticker, cleaned)
        return {**self._peer_view(ticker, cleaned), "fetched": new}

    def clear_peers(self, email: str, ticker: str) -> dict:
        """Forget every peer the user picked for a company."""
        ticker = ticker.upper()
        if self.peers_store is not None:
            self.peers_store.set_peers(email, ticker, [])
        return self._peer_view(ticker, [])

    def _peer_view(self, ticker: str, peers: list[str]) -> dict:
        target = self.numbers.get(ticker)
        compared = []
        for peer in peers:
            entry = self.numbers.get(peer)
            if entry is not None:
                compared.append((peer, entry["financials"]))
        scorecard = (
            build_scorecard(ticker, target["financials"], compared)
            if compared
            else []
        )
        return {
            "ticker": ticker,
            "peers": list(peers),
            "scorecard": [table.model_dump() for table in scorecard],
        }
