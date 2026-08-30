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
