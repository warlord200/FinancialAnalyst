"""Build SEC company-facts JSON fixtures with known numbers.

The values follow a deliberately round set of numbers so that
computation assertions can be checked against worked examples.

Revenue: 100 -> 150 over 5 years (FY2020..FY2025), so the 5-year
revenue CAGR is (150/100)**(1/5) - 1.
"""


def entry(end: str, val: float, fy: int, filed: str, form: str = "10-K", fp: str = "FY") -> dict:
    return {
        "end": end,
        "val": val,
        "accn": f"0001-{fy}",
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
        "frame": f"CY{fy}",
    }


def unit_entries(values: dict[int, float], filed_year_offset: int = 1) -> list[dict]:
    entries = []
    for fy, val in values.items():
        end = f"{fy}-12-31"
        filed = f"{fy + filed_year_offset}-01-20"
        entries.append(entry(end, val, fy, filed))
    return entries


def make_facts(year_values: dict[str, dict[int, float]]) -> dict:
    concepts = {}
    for tag, values in year_values.items():
        concepts[tag] = {"units": {"USD": unit_entries(values)}}
    return {"cik": 1318605, "entityName": "FIXTURE, INC.", "facts": {"us-gaap": concepts}}
