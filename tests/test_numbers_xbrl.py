from financial_analyst.numbers.xbrl import annual_values
from tests.fixtures.xbrl_facts import entry, make_facts


def test_annual_values_takes_10k_fy_entries_per_fiscal_year():
    facts = make_facts(
        {
            "Revenues": {
                2025: 150,
                2024: 140,
                2023: 130,
            }
        }
    )
    result = annual_values(facts, ["Revenues"])
    assert result == {2025: 150.0, 2024: 140.0, 2023: 130.0}


def test_annual_values_latest_filed_wins_on_restatement():
    facts = {
        "cik": 1,
        "entityName": "TEST, INC.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            entry("2024-12-31", 140, 2024, "2025-01-20"),
                            entry("2024-12-31", 135, 2024, "2025-03-10", form="10-K/A"),
                        ]
                    }
                }
            }
        },
    }
    result = annual_values(facts, ["Revenues"])
    assert result == {2024: 135.0}


def test_annual_values_ignores_quarterly_and_non_10k_entries():
    facts = make_facts({"Revenues": {2024: 140}})
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"].extend(
        [
            entry("2024-09-30", 100, 2024, "2024-10-20", form="10-Q", fp="Q3"),
            entry("2024-12-31", 145, 2024, "2025-01-20", form="8-K", fp="FY"),
        ]
    )
    result = annual_values(facts, ["Revenues"])
    assert result == {2024: 140.0}


def test_annual_values_returns_empty_for_missing_concept():
    facts = make_facts({"Revenues": {2024: 140}})
    assert annual_values(facts, ["GrossProfit"]) == {}


def test_annual_values_merges_fallback_tags_to_fill_gaps():
    facts = make_facts(
        {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                2023: 53823000000,
                2024: 81462000000,
            },
            "Revenues": {
                2020: 21461000000,
                2021: 24578000000,
                2022: 31536000000,
            },
        }
    )
    result = annual_values(
        facts,
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ],
    )
    assert result == {
        2023: 53823000000.0,
        2024: 81462000000.0,
        2020: 21461000000.0,
        2021: 24578000000.0,
        2022: 31536000000.0,
    }


def test_annual_values_primary_tag_value_wins_over_fallback():
    facts = make_facts(
        {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {2018: 21461268000},
            "Revenues": {2018: 7000132000},
        }
    )
    result = annual_values(
        facts,
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ],
    )
    assert result == {2018: 21461268000.0}


def test_annual_values_maps_comparative_rows_in_one_10k_to_their_own_fiscal_year():
    """A single 10-K accession stamps every comparative period with the
    accession's fy. Net income for FY2023/24/25 is reported inside the FY2025
    10-K with all rows fy=2025; each value must land on its own period."""
    facts = {
        "cik": 1318605,
        "entityName": "TESLA, INC.",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            entry("2023-12-31", 14997000000, 2025, "2026-01-29"),
                            entry("2024-12-31", 7091000000, 2025, "2026-01-29"),
                            entry("2025-12-31", 3794000000, 2025, "2026-01-29"),
                        ]
                    }
                }
            }
        },
    }
    result = annual_values(facts, ["NetIncomeLoss"])
    assert result == {
        2023: 14997000000.0,
        2024: 7091000000.0,
        2025: 3794000000.0,
    }


def test_annual_values_uses_period_end_year_for_non_december_fiscal_year():
    """AAPL's fiscal year ends in late September. All three rows in the FY2025
    10-K share fy=2025 but their periods end 2023/2024/2025-09-*; the value
    must be attributed to the year the period actually ends in."""
    facts = {
        "cik": 320193,
        "entityName": "APPLE INC.",
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            entry("2023-09-30", 96995000000, 2025, "2025-10-31"),
                            entry("2024-09-28", 93736000000, 2025, "2025-10-31"),
                            entry("2025-09-27", 112010000000, 2025, "2025-10-31"),
                        ]
                    }
                }
            }
        },
    }
    result = annual_values(facts, ["NetIncomeLoss"])
    assert result == {
        2023: 96995000000.0,
        2024: 93736000000.0,
        2025: 112010000000.0,
    }
