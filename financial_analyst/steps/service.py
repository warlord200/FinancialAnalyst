"""The dossier step service: reads the shared numbers layer, the shared
content corpus, and the per-user step state, and composes step responses.

Step 1 (the one-pager), step 3 tables, and step 5 (valuation) are pure
derivations from the numbers layer. Step 5 is hard-gated: it is not
computed until the Step 1 gate is accepted and the user marks steps 2-4
done in the per-user step state, so the price cannot bias the earlier
analysis. Steps 2-4 are source-tagged artifacts produced by the generation
framework over the shared corpus; they are cached per ticker so a repeat
view is instant and stable. Step 6 (the thesis) is gated like valuation
and drafts the same way as steps 2-4: a read-only, source-tagged thesis
document the user reviews but does not edit.
"""

from financial_analyst.steps import DONE_STEPS, STEP_ONE
from financial_analyst.steps.business_swot import ARTIFACT_TYPE, build_business_swot
from financial_analyst.steps.financials import ARTIFACT_TYPE as FINANCIALS_TYPE
from financial_analyst.steps.financials import build_financials
from financial_analyst.steps.generation import NoSourceError
from financial_analyst.steps.one_pager import build_one_pager
from financial_analyst.steps.peers import build_scorecard
from financial_analyst.steps.strategy import ARTIFACT_TYPE as STRATEGY_TYPE
from financial_analyst.steps.strategy import build_strategy
from financial_analyst.steps.thesis import THESIS_SECTIONS, THESIS_TYPE, build_thesis
from financial_analyst.steps.valuation import market_multiples
from financial_analyst.steps.valuation import valuation as compute_valuation


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

    def _done_map(self, email: str, ticker: str) -> dict[str, bool]:
        done_steps = self.state.get_done_steps(email, ticker) if self.state else []
        return {str(step): step in done_steps for step in DONE_STEPS}

    def _gate_accepted(self, email: str, ticker: str) -> bool:
        gate = self.state.get_gate(email, ticker, STEP_ONE) if self.state else None
        return gate is not None and gate["status"] == "accepted"

    def _gated_missing(self, email: str, ticker: str) -> list[int]:
        """The prerequisites that keep valuation/thesis locked.

        Step 5-6 unlock exactly when the Step 1 gate is accepted and every
        step in ``DONE_STEPS`` is marked done. Missing prerequisites are
        reported ascending: step 1 first when the gate is not accepted,
        then the steps 2-4 that are not yet marked done.
        """
        done_map = self._done_map(email, ticker)
        missing: list[int] = []
        if not self._gate_accepted(email, ticker):
            missing.append(STEP_ONE)
        missing.extend(step for step in DONE_STEPS if not done_map[str(step)])
        return missing

    def done_status(self, email: str, ticker: str) -> dict | None:
        """The company's dossier progress: gate state and done-marks.

        Returns None when the ticker has no numbers, so the caller can 404.
        This is the read the workspace uses to render the step strip: the
        gate is the Step 1 decision and the done-marks cover steps 2-4.
        """
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        gate = self.state.get_gate(email, ticker, STEP_ONE) if self.state else None
        return {"ticker": ticker, "gate": gate, "done": self._done_map(email, ticker)}

    def mark_done(self, email: str, ticker: str, step: int) -> dict | None:
        """Record that the user has reviewed and finished a step.

        Done-marks live on steps 2-4 only; the accept/reject gate on step 1
        is separate and does not count. Returns None when the ticker has no
        numbers.
        """
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        self.state.set_done(email, ticker, step)
        return self.done_status(email, ticker)

    def unmark_done(self, email: str, ticker: str, step: int) -> dict | None:
        """Reopen a step the user had marked done."""
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        self.state.clear_done(email, ticker, step)
        return self.done_status(email, ticker)

    def valuation(
        self,
        email: str,
        ticker: str,
        discount_rate: float | None = None,
        growth: float | None = None,
    ) -> dict | None:
        """The Step 5 valuation, locked until the gate is accepted and the
        user marks steps 2-4 done.

        Returns a locked payload with ``missing_steps`` until the gate is
        accepted and every gating step is marked done, so the caller never
        sees a price-based analysis before they have reviewed steps 1-4.
        When unlocked the valuation is computed on demand from the shared
        numbers layer and the user's price (including any manual override);
        peers from the user's peer list are pulled in at their own current
        prices (fetched lazily). Returns None when the ticker has no
        numbers.
        """
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        done_map = self._done_map(email, ticker)
        missing = self._gated_missing(email, ticker)
        payload = {
            "ticker": ticker,
            "locked": bool(missing),
            "done": done_map,
            "missing_steps": missing,
        }
        if missing:
            return payload

        numbers = self.numbers.get(ticker)
        price_payload = numbers.get("price") or {}
        effective = price_payload.get("effective") or {}
        history = price_payload.get("history") or []

        overrides = {}
        if discount_rate is not None:
            overrides["discount_rate"] = discount_rate
        if growth is not None:
            overrides["growth"] = growth
        valuation = compute_valuation(
            numbers["financials"],
            effective.get("price"),
            history,
            **overrides,
        )

        peers = self.peers_store.list_peers(email, ticker) if self.peers_store else []
        peer_multiples = []
        for peer in peers:
            entry = self.numbers.get(peer)
            if entry is None:
                continue
            self.numbers.ensure_price(peer)
            entry = self.numbers.get(peer)
            peer_price = ((entry.get("price") or {}).get("effective") or {}).get("price")
            peer_multiples.append(
                {"ticker": peer, **market_multiples(entry["financials"], peer_price)}
            )
        valuation["peers"] = peer_multiples
        return {**payload, "valuation": valuation}

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

    def _thesis_draft(self, ticker: str) -> dict | None:
        """The shared, source-tagged thesis draft for a ticker.

        Generated once through the generation framework over the dossier
        corpus and cached per ticker, so a repeat view is instant and every
        user sees the same grounded thesis. Returns None when there is no
        generator or no corpus to draft over.
        """
        cached = self.drafts.get_draft(ticker, THESIS_TYPE) if self.drafts else None
        if cached is not None:
            return cached
        if self.generator is None:
            return None
        try:
            artifact = build_thesis(self.generator, ticker)
        except NoSourceError:
            return None
        draft = artifact.model_dump()
        if self.drafts is not None:
            self.drafts.set_draft(ticker, THESIS_TYPE, draft)
        return draft

    def _thesis_doc(self, draft: dict) -> dict:
        """The read-only thesis document, one canonical section per heading.

        Content is taken from the grounded draft in canonical order, so the
        document mirrors the draft without re-stating its source tags; the
        API keeps the draft alongside for the source-grounding display.
        """
        content_by_key = {s["key"]: s["content"] for s in draft.get("sections", [])}
        sections = [
            {
                "key": spec.key,
                "heading": spec.heading,
                "content": content_by_key.get(spec.key, ""),
            }
            for spec in THESIS_SECTIONS
        ]
        return {"sections": sections}

    def thesis(self, email: str, ticker: str) -> dict | None:
        """The Step 6 thesis, locked until the gate is accepted and the user
        marks steps 2-4 done.

        Returns a locked payload with ``missing_steps`` until the gate is
        accepted and every gating step is marked done, mirroring valuation:
        the thesis is the final synthesis, so it is only composed after the
        user has reviewed the dossier. When unlocked the response carries
        the grounded draft and the read-only thesis document seeded from it.
        The thesis is not editable: repeat views return the same cached
        draft, and re-analysis rebuilds the shared draft. Returns None when
        the ticker has no numbers, or when it is unlocked but there is no
        corpus to draft over.
        """
        ticker = ticker.upper()
        if self.numbers.get(ticker) is None:
            return None
        done_map = self._done_map(email, ticker)
        missing = self._gated_missing(email, ticker)
        if missing:
            return {
                "ticker": ticker,
                "locked": True,
                "done": done_map,
                "missing_steps": missing,
            }
        draft = self._thesis_draft(ticker)
        if draft is None:
            return None
        return {
            "ticker": ticker,
            "locked": False,
            "done": done_map,
            "missing_steps": [],
            "draft": draft,
            "thesis": self._thesis_doc(draft),
        }
