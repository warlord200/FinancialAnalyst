from pathlib import Path

from financial_analyst.reader.sec_html_reader import SECHtmlReader


def test_load_data_splits_into_item_sections():
    fixture = Path(__file__).parent / "fixtures" / "tsla_2025_sample.htm"
    reader = SECHtmlReader()
    docs = reader.load_data(
        str(fixture), extra_info={"ticker": "TSLA", "fiscal_year": 2025}
    )

    assert len(docs) == 4
    items = [d.metadata["item"] for d in docs]
    assert items == ["ITEM 1", "ITEM 1A", "ITEM 7", "ITEM 8"]

    for d in docs:
        assert d.metadata["ticker"] == "TSLA"
        assert d.metadata["fiscal_year"] == 2025
        assert "<html" not in d.text
        assert "<p>" not in d.text


def test_load_data_parses_ticker_and_year_from_path(tmp_path):
    fixture = tmp_path / "2024" / "TSLA.htm"
    fixture.parent.mkdir()
    fixture.write_text(
        "<html><body><h2>Item 7.</h2><p>MD&A text</p></body></html>",
        encoding="utf-8",
    )
    reader = SECHtmlReader()
    docs = reader.load_data(str(fixture))

    assert len(docs) == 1
    assert docs[0].metadata["ticker"] == "TSLA"
    assert docs[0].metadata["fiscal_year"] == 2024
    assert docs[0].metadata["item"] == "ITEM 7"


def test_load_data_skips_empty_sections():
    fixture = Path(__file__).parent / "fixtures" / "tsla_2025_sample.htm"
    reader = SECHtmlReader()
    docs = reader.load_data(str(fixture), extra_info={"ticker": "TSLA", "fiscal_year": 2025})
    for d in docs:
        assert d.text.strip()


def test_load_data_handles_xml_declaration(tmp_path):
    fixture = tmp_path / "2025" / "TSLA.htm"
    fixture.parent.mkdir()
    fixture.write_text(
        "<?xml version='1.0' encoding='ASCII'?>\n"
        "<html><body><h2>Item 7.</h2><p>Revenue grew strongly.</p></body></html>",
        encoding="utf-8",
    )
    reader = SECHtmlReader()
    docs = reader.load_data(str(fixture), extra_info={"ticker": "TSLA", "fiscal_year": 2025})

    assert len(docs) == 1
    assert docs[0].metadata["item"] == "ITEM 7"
    assert "Revenue grew" in docs[0].text


def test_load_data_passes_through_extra_metadata(tmp_path):
    fixture = tmp_path / "2025" / "TSLA.htm"
    fixture.parent.mkdir()
    fixture.write_text(
        "<html><body><h2>Item 1.</h2><p>Business text.</p></body></html>",
        encoding="utf-8",
    )
    reader = SECHtmlReader()
    docs = reader.load_data(
        str(fixture), extra_info={"ticker": "TSLA", "fiscal_year": 2025, "filing": "10-K"}
    )

    assert len(docs) == 1
    assert docs[0].metadata["ticker"] == "TSLA"
    assert docs[0].metadata["fiscal_year"] == 2025
    assert docs[0].metadata["item"] == "ITEM 1"
    assert docs[0].metadata["filing"] == "10-K"
