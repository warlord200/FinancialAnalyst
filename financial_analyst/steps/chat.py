"""Step-scoped chat with a search-everything escape hatch.

Chat is supported for the dossier steps that draft over the corpus (steps
2-4). Each such step is scoped to its own source items by default — step 2
reads Item 1/1A, step 3 reads Item 7/8, step 4 reads Item 5/7 — and a
per-step "search everything" toggle lifts the scope to the whole corpus.
Steps without a defined scope (1, 5, 6) do not support chat.

Answers are grounded the same way artifact sections are: the LLM answers
from the numbered source passages it was shown, cites which passages back
the answer (``source_refs``), and the answer's citations are derived from
those cited chunks' own metadata — never from strings the model wrote. An
answer that fails grounding is sent back once with the violations; if it
still fails, :class:`ArtifactValidationError` is raised so the caller can
surface that the answer could not be grounded.
"""

from financial_analyst.steps import STEP_SCOPES
from financial_analyst.steps.generation import (
    ArtifactValidationError,
    NoSourceError,
    cited_chunks,
    evidence_violations,
    parse_json,
    render_chunks,
)


class UnsupportedStepError(Exception):
    def __init__(self, step: int) -> None:
        super().__init__(f"Chat is not supported for step {step}.")
        self.step = step


class ChatService:
    def __init__(self, retriever, llm, top_k: int = 6, max_attempts: int = 2) -> None:
        self.retriever = retriever
        self.llm = llm
        self.top_k = top_k
        self.max_attempts = max_attempts

    def answer(
        self,
        ticker: str,
        question: str,
        step: int,
        search_all: bool = False,
    ) -> dict:
        ticker = ticker.upper()
        if step not in STEP_SCOPES:
            raise UnsupportedStepError(step)
        scoped_items = None if search_all else list(STEP_SCOPES[step])
        chunks = self.retriever.retrieve(
            ticker,
            question,
            items=scoped_items,
            top_k=self.top_k,
        )
        if not chunks:
            raise NoSourceError(ticker, f"no source chunks for step {step}")
        prompt = self._prompt(ticker, question, step, chunks)
        for attempt in range(self.max_attempts):
            answer, violations = self._attempt(step, search_all, scoped_items, prompt, chunks)
            if violations is None:
                return answer
            if attempt < self.max_attempts - 1:
                prompt = self._repair_prompt(prompt, violations)
        raise ArtifactValidationError("chat", violations)

    def _attempt(
        self,
        step: int,
        search_all: bool,
        scoped_items: list[str] | None,
        prompt: str,
        chunks,
    ) -> tuple[dict | None, list[str] | None]:
        text = self.llm.complete(prompt).text
        data = parse_json(text)
        if data is None:
            return None, ["response was not valid JSON"]
        cited, violations = cited_chunks(data.get("source_refs", []), chunks)
        if violations:
            return None, violations
        answer = data.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            return None, ["answer is empty"]
        evidence = data.get("evidence", [])
        if evidence is None:
            evidence = []
        if isinstance(evidence, str):
            evidence = [evidence]
        evidence_violations_list = evidence_violations(evidence, chunks)
        if evidence_violations_list:
            return None, evidence_violations_list
        return (
            {
                "ticker": chunks[0].ticker or "",
                "step": step,
                "search_all": search_all,
                "scope": {
                    "items": list(scoped_items) if scoped_items else None,
                    "fiscal_year": None,
                },
                "answer": answer,
                "sources": [chunk.to_dict() for chunk in cited],
                "evidence": list(evidence),
            },
            None,
        )

    @staticmethod
    def _prompt(ticker: str, question: str, step: int, chunks) -> str:
        return "\n\n".join(
            [
                f"You are answering a question about {ticker} in step {step} of a financial dossier.",
                "Source passages (numbered; only these may be used):",
                render_chunks(chunks),
                (
                    "Answer the question in 2-5 sentences of factual prose based ONLY on the source "
                    'passages. Return ONLY a JSON object: {"answer": "<prose>", "source_refs": '
                    '[<numbers of the passages above that back this answer>], "evidence": '
                    '["<verbatim sentence from a cited passage>"]}.'
                ),
                (
                    'Rules: "source_refs" must list at least one of the numbered passages above and '
                    'only passages this answer actually draws on. "evidence" entries must be exact '
                    "quotes taken verbatim from those passages (whitespace normalized)."
                ),
            ]
        )

    @staticmethod
    def _repair_prompt(prompt: str, violations: list[str]) -> str:
        bulleted = "\n".join(f"- {v}" for v in violations)
        return (
            f"{prompt}\n\nThe previous answer was rejected because:\n{bulleted}\n"
            "Fix every problem and return ONLY the corrected JSON object."
        )
