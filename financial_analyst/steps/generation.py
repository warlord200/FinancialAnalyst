"""The source-tagged artifact generation framework.

Every dossier step that produces a drafted artifact (steps 2-4 and the
thesis) goes through this framework. It drives a small RAG loop per
section: retrieve source chunks scoped to the section's Item and fiscal
year, ask the LLM for a structured section, then *enforce* the grounding
before accepting it.

The LLM never writes source-tag values by hand — it cites the numbered
source passages it was shown (``source_refs``), and the framework derives
each section's source tags from the cited chunks' own metadata (Item,
fiscal year, filing). Tags are therefore correct by construction and can
never reference material the model did not see:

- every section must cite at least one source passage,
- every citation must be a passage the model was shown,
- every evidence quote must appear verbatim in the source material.

A section that fails enforcement is sent back once with the violations;
if it still fails, generation raises :class:`ArtifactValidationError` so
the caller can surface that the draft could not be grounded.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class SourceTag(BaseModel):
    type: Literal["fiscal_year", "filing", "item", "xbrl_fact"]
    value: str


class ArtifactSection(BaseModel):
    key: str
    heading: str
    content: str
    sources: list[SourceTag] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class Scope(BaseModel):
    items: list[str] = Field(default_factory=list)
    fiscal_year: int | None = None


class Artifact(BaseModel):
    ticker: str
    artifact_type: str
    fiscal_year: int | None = None
    scope: Scope = Field(default_factory=Scope)
    generated_at: str
    sections: list[ArtifactSection] = Field(default_factory=list)


@dataclass
class SectionSpec:
    key: str
    heading: str
    query: str
    instruction: str = ""
    items: tuple[str, ...] = ("ITEM 1", "ITEM 1A")
    context_from: tuple[str, ...] = ()
    top_k: int = 4


class NoSourceError(Exception):
    def __init__(self, ticker: str, reason: str = "") -> None:
        suffix = f": {reason}" if reason else ""
        super().__init__(f"No source material for {ticker}{suffix}")
        self.ticker = ticker


class ArtifactValidationError(Exception):
    def __init__(self, key: str, violations: list[str]) -> None:
        super().__init__(
            f"Section '{key}' failed source-tag enforcement: {'; '.join(violations)}"
        )
        self.key = key
        self.violations = violations


def norm(text: str) -> str:
    """Normalize text for verbatim-evidence comparisons: collapse
    whitespace and case. Shared by artifact and chat grounding."""
    return " ".join(text.split()).lower()


def parse_json(text: str) -> dict | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(stripped[start : i + 1])
                except json.JSONDecodeError:
                    return None
                return data if isinstance(data, dict) else None
    return None


def tags_for_chunk(chunk) -> list[SourceTag]:
    tags = []
    if chunk.item:
        tags.append(SourceTag(type="item", value=chunk.item))
    if chunk.fiscal_year is not None:
        tags.append(SourceTag(type="fiscal_year", value=str(chunk.fiscal_year)))
    if chunk.filing:
        tags.append(SourceTag(type="filing", value=chunk.filing))
    return tags


def cited_chunks(refs, chunks) -> tuple[list, list[str]]:
    """Validate the LLM's numbered source references against the passages
    it was shown, returning the cited chunks plus any violations. Shared by
    the artifact and chat grounding loops so both enforce the same rule:
    every citation must point at a passage the model actually saw."""
    if isinstance(refs, (int, str)):
        refs = [refs]
    cited: list = []
    violations: list[str] = []
    if not refs:
        return cited, ["cites no source passages"]
    for ref in refs:
        try:
            index = int(ref)
        except (TypeError, ValueError):
            violations.append(f"source reference is not a passage number: {ref!r}")
            continue
        if not (1 <= index <= len(chunks)):
            violations.append(f"source reference not among the passages shown: {index}")
            continue
        if chunks[index - 1] not in cited:
            cited.append(chunks[index - 1])
    return cited, violations


def evidence_violations(evidence: list, chunks) -> list[str]:
    """Reject evidence quotes that do not appear verbatim in the passages
    the model was shown. Shared by the artifact and chat grounding loops."""
    corpus = " ".join(norm(c.text) for c in chunks)
    return [
        f"evidence not found verbatim in source material: {quote[:64]!r}"
        for quote in evidence
        if norm(str(quote)) not in corpus
    ]


def validate_section(section: ArtifactSection, chunks) -> list[str]:
    violations: list[str] = []
    if not section.sources:
        violations.append("section has no source tags")
    violations.extend(evidence_violations(section.evidence, chunks))
    return violations


def render_chunks(chunks) -> str:
    lines = []
    for i, chunk in enumerate(chunks, 1):
        meta = ", ".join(
            part
            for part in [
                chunk.item,
                f"FY{chunk.fiscal_year}" if chunk.fiscal_year is not None else None,
                chunk.filing,
            ]
            if part
        )
        lines.append(f"[{i}] ({meta}) {chunk.text}")
    return "\n".join(lines)


class ArtifactGenerator:
    def __init__(self, retriever, llm, max_attempts: int = 2) -> None:
        self.retriever = retriever
        self.llm = llm
        self.max_attempts = max_attempts

    def generate(
        self,
        ticker: str,
        artifact_type: str,
        sections: list[SectionSpec] | tuple[SectionSpec, ...],
        fiscal_year: int | None = None,
    ) -> Artifact:
        ticker = ticker.upper()
        if fiscal_year is None:
            fiscal_year = self._latest_year_with_sources(ticker, sections)

        generated: list[ArtifactSection] = []
        for spec in sections:
            chunks = self.retriever.retrieve(
                ticker,
                spec.query,
                items=list(spec.items),
                fiscal_year=fiscal_year,
                top_k=spec.top_k,
            )
            if not chunks:
                raise NoSourceError(ticker, f"no source chunks for section '{spec.key}'")
            generated.append(self._draft_section(ticker, fiscal_year, spec, chunks, generated))

        return Artifact(
            ticker=ticker,
            artifact_type=artifact_type,
            fiscal_year=fiscal_year,
            scope=Scope(
                items=list(dict.fromkeys(item for spec in sections for item in spec.items)),
                fiscal_year=fiscal_year,
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
            sections=generated,
        )

    def _latest_year_with_sources(
        self,
        ticker: str,
        sections: list[SectionSpec] | tuple[SectionSpec, ...],
    ) -> int:
        """Pick the fiscal year to draft the artifact from.

        Years are considered newest first. The first year that has source
        chunks for *every* requested item wins, so a partial year (for
        example a fiscal year that only holds 10-Qs, which carry no Item
        7/8, or a 10-Q whose Item 5 is "Other Information" rather than the
        market-for-shares item) is skipped in favour of the most recent
        complete annual filing.
        """
        years = self.retriever.fiscal_years(ticker)
        if not years:
            raise NoSourceError(ticker, "no filings indexed")
        if not sections:
            raise NoSourceError(ticker, "no sections requested")
        requested_items = list(
            dict.fromkeys(item for spec in sections for item in spec.items)
        )
        for year in sorted(years, reverse=True):
            if not self._year_has_all_items(ticker, sections[0].query, requested_items, year):
                continue
            return year
        raise NoSourceError(ticker, "no source chunks for the requested items")

    def _year_has_all_items(
        self, ticker: str, query: str, items: list[str], fiscal_year: int
    ) -> bool:
        if not items:
            return bool(
                self.retriever.retrieve(
                    ticker, query, items=None, fiscal_year=fiscal_year, top_k=1
                )
            )
        return all(
            self.retriever.retrieve(
                ticker, query, items=[item], fiscal_year=fiscal_year, top_k=1
            )
            for item in items
        )

    def _draft_section(
        self,
        ticker: str,
        fiscal_year: int,
        spec: SectionSpec,
        chunks,
        prior: list[ArtifactSection],
    ) -> ArtifactSection:
        prompt = self._section_prompt(ticker, fiscal_year, spec, chunks, prior)
        for attempt in range(self.max_attempts):
            section, violations = self._attempt(spec, prompt, chunks)
            if not violations:
                return section
            if attempt < self.max_attempts - 1:
                prompt = self._repair_prompt(prompt, violations)
        raise ArtifactValidationError(spec.key, violations)

    def _attempt(
        self, spec: SectionSpec, prompt: str, chunks
    ) -> tuple[ArtifactSection | None, list[str]]:
        text = self.llm.complete(prompt).text
        data = parse_json(text)
        if data is None:
            return None, ["response was not valid JSON"]
        cited, violations = cited_chunks(data.get("source_refs", []), chunks)
        if violations:
            return None, violations
        sources: list[SourceTag] = []
        for chunk in cited:
            for tag in tags_for_chunk(chunk):
                if tag not in sources:
                    sources.append(tag)
        try:
            section = ArtifactSection(
                key=spec.key,
                heading=spec.heading,
                content=data["content"],
                sources=sources,
                evidence=data.get("evidence", []),
            )
        except (ValidationError, KeyError) as exc:
            return None, [f"invalid section shape: {exc}"]
        return section, validate_section(section, chunks)

    def _section_prompt(
        self,
        ticker: str,
        fiscal_year: int,
        spec: SectionSpec,
        chunks,
        prior: list[ArtifactSection],
    ) -> str:
        parts = [
            f"You are drafting the '{spec.heading}' section of a {ticker} dossier.",
            f"Source material: the fiscal {fiscal_year} 10-K filings.",
            "Source passages (numbered; only these may be used):",
            render_chunks(chunks),
        ]
        if spec.context_from:
            context = "\n\n".join(
                f"{s.heading}: {s.content}" for s in prior if s.key in spec.context_from
            )
            parts += [
                "Earlier sections you already drafted (for context only; do not cite these):",
                context,
            ]
        parts += [
            f"Write the section as 3-6 sentences of factual prose based ONLY on the source passages. {spec.instruction}",
            'Return ONLY a JSON object: {"content": "<prose>", "source_refs": [<numbers of the passages above that back this section>], "evidence": ["<verbatim sentence from a cited passage>"]}.',
            'Rules: "source_refs" must list at least one of the numbered passages above and only passages this section actually draws on. "evidence" entries must be exact quotes taken verbatim from those passages (whitespace normalized).',
        ]
        return "\n\n".join(parts)

    @staticmethod
    def _repair_prompt(prompt: str, violations: list[str]) -> str:
        bulleted = "\n".join(f"- {v}" for v in violations)
        return (
            f"{prompt}\n\nThe previous draft was rejected because:\n{bulleted}\n"
            "Fix every problem and return ONLY the corrected JSON object."
        )
