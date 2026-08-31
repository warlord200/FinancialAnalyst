"""The source-tagged artifact generation framework.

Every dossier step that produces a drafted artifact (steps 2-4 and the
thesis) goes through this framework. It drives a small RAG loop per
section: retrieve source chunks scoped to the section's Item and fiscal
year, ask the LLM for a structured section, then *enforce* the source
tags before accepting it:

- every section must carry at least one source tag,
- every source tag must resolve to a source chunk the model was shown,
- every evidence quote must appear verbatim in that source material.

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


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _parse_json(text: str) -> dict | None:
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


def _tag_matches_chunks(tag: SourceTag, chunks) -> bool:
    if tag.type == "item":
        return any(c.item == tag.value for c in chunks)
    if tag.type == "fiscal_year":
        wanted = tag.value.strip().upper().removeprefix("FY")
        return any(
            c.fiscal_year is not None and str(c.fiscal_year) == wanted for c in chunks
        )
    if tag.type == "filing":
        return any(c.filing == tag.value for c in chunks)
    if tag.type == "xbrl_fact":
        return any(getattr(c, "fact_key", None) == tag.value for c in chunks)
    return False


def _validate_section(section: ArtifactSection, chunks) -> list[str]:
    violations: list[str] = []
    if not section.sources:
        violations.append("section has no source tags")
    for tag in section.sources:
        if not _tag_matches_chunks(tag, chunks):
            violations.append(
                f"source tag not found in source material: {tag.type}={tag.value}"
            )
    corpus = " ".join(_norm(c.text) for c in chunks)
    for quote in section.evidence:
        if _norm(quote) not in corpus:
            violations.append(
                f"evidence not found verbatim in source material: {quote[:64]!r}"
            )
    return violations


def _render_chunks(chunks) -> str:
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
            years = self.retriever.fiscal_years(ticker)
            if not years:
                raise NoSourceError(ticker, "no filings indexed")
            fiscal_year = max(years)

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
        data = _parse_json(text)
        if data is None:
            return None, ["response was not valid JSON"]
        try:
            section = ArtifactSection(
                key=spec.key,
                heading=spec.heading,
                content=data["content"],
                sources=data.get("sources", []),
                evidence=data.get("evidence", []),
            )
        except (ValidationError, KeyError) as exc:
            return None, [f"invalid section shape: {exc}"]
        return section, _validate_section(section, chunks)

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
            _render_chunks(chunks),
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
            'Return ONLY a JSON object: {"content": "<prose>", "sources": [{"type": "item"|"fiscal_year"|"filing"|"xbrl_fact", "value": "..."}], "evidence": ["<verbatim sentence from a passage>"]}.',
            'Rules: "sources" must reference only the passages shown (their Item, fiscal year, or filing). "evidence" entries must be exact quotes taken verbatim from the passages (whitespace normalized). At least one source is required.',
        ]
        return "\n\n".join(parts)

    @staticmethod
    def _repair_prompt(prompt: str, violations: list[str]) -> str:
        bulleted = "\n".join(f"- {v}" for v in violations)
        return (
            f"{prompt}\n\nThe previous draft was rejected because:\n{bulleted}\n"
            "Fix every problem and return ONLY the corrected JSON object."
        )
