# financial_analyst/analysis/report_generator.py
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from financial_analyst.indexing.CustomDocs import CustomDocs

VERDICT_LABELS = ("bullish", "neutral", "bearish")

SECTION_QUERIES = {
    "Business Overview": (
        "Describe the company's business: what it does, its main products and services, "
        "customer segments, and principal competition. Cite the SEC Item section you used, e.g. (Item 1)."
    ),
    "Risk Factors": (
        "List the key risk factors described in the 10-K, grouped by theme (market, competition, "
        "regulatory, operational, financial). Cite the SEC Item section, e.g. (Item 1A)."
    ),
    "MD&A": (
        "Summarize management's discussion and analysis: revenue drivers, margin trends, and "
        "liquidity and capital resources outlook. Cite the SEC Item section, e.g. (Item 7)."
    ),
    "Segment Performance": (
        "Report revenue and profit for each operating segment for this fiscal year. "
        "If segments are not broken out, say so explicitly. Cite the SEC Item section."
    ),
}

FINANCIAL_HEALTH_QUERY = (
    "Summarize the balance sheet and cash flow highlights: total assets, total liabilities, "
    "cash and cash equivalents, total debt, working capital, operating cash flow. "
    "Cite the SEC Item section, e.g. (Item 8)."
)

YO_Y_METRICS = ["Revenue", "Net Income", "EPS", "Operating Margin", "Net Margin", "Free Cash Flow"]


@dataclass
class Report:
    ticker: str
    fiscal_years: list[int]
    generated_at: str
    verdict: dict
    markdown: str


class ReportGenerator:
    def __init__(self, docs_by_year: dict[int, CustomDocs], llm, ticker: str) -> None:
        self.docs_by_year = docs_by_year
        self.llm = llm
        self.ticker = ticker

    def _years(self) -> list[int]:
        return sorted(self.docs_by_year.keys(), reverse=True)

    def _query(self, year: int, question: str) -> str:
        cd = self.docs_by_year[year]
        vec_idx, summ_idx = cd.get_indexes()
        try:
            engine = vec_idx.as_query_engine(similarity_top_k=3)
            return str(engine.query(question).response)
        except Exception:
            engine = summ_idx.as_query_engine(response_mode="tree_summarize")
            return str(engine.query(question).response)

    def _latest_year(self) -> int:
        return max(self.docs_by_year.keys())

    def _executive_summary(self) -> tuple[str, dict]:
        years = self._years()
        year_list = ", ".join(str(y) for y in years)
        prompt = (
            f"Write a concise executive summary (4-5 sentences) of the fiscal {year_list} "
            f"10-K filings for {self.ticker}. Cover overall business, financial performance, and outlook. "
            f"Then output a verdict on its own line as JSON: "
            f'{{"label": "bullish"|"neutral"|"bearish", "score": <int 0-100>, '
            f'"rationale": "<one sentence>"}}'
        )
        summary = self._query(self._latest_year(), prompt)
        verdict = self._build_verdict(prompt, summary)
        return summary, verdict

    def _build_verdict(self, prompt: str, summary: str) -> dict:
        fallback = {"label": "neutral", "score": 50, "rationale": "Unable to determine verdict from filings."}
        try:
            text = self.llm.complete(prompt).text
        except Exception:
            return fallback
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return fallback
        try:
            data = json.loads(m.group(0))
            label = str(data.get("label", "")).lower()
            if label not in VERDICT_LABELS:
                return fallback
            score = int(data.get("score", 50))
            score = max(0, min(100, score))
            return {
                "label": label,
                "score": score,
                "rationale": str(data.get("rationale", "")),
            }
        except (ValueError, json.JSONDecodeError):
            return fallback

    def _section_from_filings(self, title: str, question: str) -> str:
        latest = self._latest_year()
        return self._query(latest, question)

    def _yoy_comparison(self) -> str:
        years = self._years()
        if len(years) < 2:
            return (
                "Prior year filing unavailable, so a year-over-year comparison could not be generated. "
                f"Only fiscal {years[0]} is covered."
            )
        curr, prior = years[0], years[1]
        lines = [f"| Metric | {curr} | {prior} | % Change |", "|---|---|---|---|"]
        for metric in YO_Y_METRICS:
            q = (
                f"From the 10-K for {self.ticker}, report the exact {metric.lower()} figure for "
                f"fiscal {curr} and fiscal {prior}. Return as JSON "
                f'{{"current": <number>, "prior": <number>}}. If unavailable, use null.'
            )
            curr_txt = self._query(curr, q)
            prior_txt = self._query(prior, q)
            curr_val, prior_val = self._parse_yoy_value(curr_txt), self._parse_yoy_value(prior_txt)
            change = "n/a"
            if curr_val is not None and prior_val is not None and prior_val != 0:
                change = f"{(curr_val - prior_val) / abs(prior_val) * 100:.1f}%"
            lines.append(
                f"| {metric} | {self._fmt(curr_val)} | {self._fmt(prior_val)} | {change} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _parse_yoy_value(text: str) -> float | None:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        for key in ("current", "prior", "value"):
            if data.get(key) is not None:
                try:
                    return float(str(data[key]).replace(",", "").replace("$", ""))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:,.0f}"

    def _provenance(self) -> str:
        years = self._years()
        year_list = ", ".join(str(y) for y in years)
        return (
            f"- Ticker: {self.ticker}\n"
            f"- Fiscal years covered: {year_list}\n"
            f"- Source: SEC EDGAR 10-K filings (primary documents)\n"
            f"- Generated at: {datetime.now(timezone.utc).isoformat()}\n"
        )

    def generate(self) -> Report:
        summary, verdict = self._executive_summary()
        sections = [f"# Executive Summary\n\n{summary}\n\n**Verdict:** {verdict['label'].upper()} "
                    f"({verdict['score']}/100) — {verdict['rationale']}"]
        for title, question in SECTION_QUERIES.items():
            body = self._section_from_filings(title, question)
            sections.append(f"# {title}\n\n{body}")
        sections.append(f"# YoY Trend Comparison\n\n{self._yoy_comparison()}")
        sections.append(
            f"# Financial Health\n\n{self._section_from_filings('Financial Health', FINANCIAL_HEALTH_QUERY)}"
        )
        sections.append(f"# Data Provenance\n\n{self._provenance()}")

        return Report(
            ticker=self.ticker,
            fiscal_years=self._years(),
            generated_at=datetime.now(timezone.utc).isoformat(),
            verdict=verdict,
            markdown="\n\n".join(sections),
        )
