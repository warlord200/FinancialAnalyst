"""SEC EDGAR XBRL company-facts fetching and annual-value extraction."""

from financial_analyst.net import DEFAULT_USER_AGENT, ExternalSourceError, get_with_retry

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

US_GAAP = "us-gaap"


class XBRLEdgarError(Exception):
    pass


def fetch_company_facts(
    cik: int, user_agent: str = DEFAULT_USER_AGENT
) -> dict:
    try:
        resp = get_with_retry(COMPANY_FACTS_URL.format(cik=cik), user_agent=user_agent)
    except ExternalSourceError as exc:
        raise XBRLEdgarError(f"Failed to fetch XBRL company-facts for CIK {cik}: {exc}")
    return resp.json()


def _annual_rows_for_tag(facts: dict, tag: str) -> dict[int, dict]:
    """Map fiscal year -> chosen fact row for one concept.

    Only 10-K annual (fp == "FY") entries count. A fiscal year is identified
    by the year its period ends in (the row's own ``end`` date), not by the
    accession-level ``fy`` attribute: SEC stamps every comparative period in
    a 10-K with that accession's ``fy``/``form``/``filed``, so a single 10-K
    can carry two or three comparative fiscal years that all share one ``fy``.
    Grouping by ``fy`` would land those values one to two years late. When a
    fiscal year has several filings (restatements), the latest filed row
    wins.
    """
    concept = facts.get(tag)
    if not concept:
        return {}
    best: dict[int, dict] = {}
    for unit in concept.get("units", {}).values():
        for item in unit:
            form = item.get("form", "")
            if not form.startswith("10-K") or item.get("fp") != "FY":
                continue
            end = item.get("end")
            if not end:
                continue
            fiscal_year = int(end[:4])
            filed = item.get("filed", "")
            current = best.get(fiscal_year)
            if current is None or filed > current["filed"]:
                best[fiscal_year] = {
                    "val": float(item["val"]),
                    "end": end,
                    "filed": filed,
                }
    return best


def annual_rows(company_facts: dict, tags: list[str]) -> dict[int, dict]:
    """Map fiscal year -> chosen fact row, merging the candidate tags.

    Each row carries ``val`` (the annual value), ``end`` (the period end
    date), and ``filed``. The first tag is preferred: fallback tags only fill
    fiscal years the primary tag does not cover. ``annual_values`` and the
    ``fiscal_year_ends`` map are both projections of this selection, so a
    value and its fiscal-year-end date always come from the same row.
    """
    facts = company_facts.get("facts", {}).get(US_GAAP, {})
    merged: dict[int, dict] = {}
    for tag in tags:
        for fiscal_year, row in _annual_rows_for_tag(facts, tag).items():
            if fiscal_year not in merged:
                merged[fiscal_year] = row
    return merged


def annual_values(company_facts: dict, tags: list[str]) -> dict[int, float]:
    """Map fiscal year -> annual value, merging the candidate tags.

    Only 10-K annual (fp == "FY") entries count. Each value is attributed to
    the fiscal year its own period ends in (the row's ``end`` year, not the
    accession ``fy``). When a fiscal year has several filings
    (restatements), the latest filed entry wins. The first tag is preferred:
    fallback tags only fill fiscal years the primary tag does not cover.
    """
    return {
        fiscal_year: row["val"]
        for fiscal_year, row in annual_rows(company_facts, tags).items()
    }
