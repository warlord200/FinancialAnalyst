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


def annual_values(company_facts: dict, tags: list[str]) -> dict[int, float]:
    """Map fiscal year -> annual value, merging the candidate tags.

    Only 10-K annual (fp == "FY") entries count. When a fiscal year has
    several filings (restatements), the latest filed entry wins. The first
    tag is preferred: fallback tags only fill fiscal years the primary tag
    does not cover.
    """
    facts = company_facts.get("facts", {}).get(US_GAAP, {})
    result: dict[int, float] = {}
    for tag in tags:
        concept = facts.get(tag)
        if not concept:
            continue
        by_year: dict[int, tuple[str, float]] = {}
        for unit in concept.get("units", {}).values():
            for item in unit:
                form = item.get("form", "")
                if not form.startswith("10-K") or item.get("fp") != "FY":
                    continue
                fy = item.get("fy")
                if fy is None:
                    continue
                filed = item.get("filed", "")
                if fy not in by_year or filed > by_year[fy][0]:
                    by_year[fy] = (filed, float(item["val"]))
        for fy, (_, val) in by_year.items():
            if fy not in result:
                result[fy] = val
    return result
