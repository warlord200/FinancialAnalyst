"""Unit tests for the Step 6 thesis (T12): the draft builder that seeds
the thesis document, and the per-user thesis store that persists the
user's edits.

The draft is produced through the generation framework over the corpus:
six grounded sections (what I hold, why, key assumptions, what would
change my mind, devil's advocate, open research gaps), each citing the
passages it drew on. The devil's advocate section is where the "argue
the opposite side with grounded sources" requirement lives: its query
and instruction must explicitly point at the negative evidence.

The store is per-user and per-ticker, mirroring the other per-user state
(done-marks, peer lists), so re-analysis that rebuilds the shared corpus
and shared drafts never touches a saved thesis.
"""

import pytest

from financial_analyst.steps.generation import ArtifactGenerator
from financial_analyst.steps.state import ThesisStore
from financial_analyst.steps.thesis import (
    THESIS_SECTIONS,
    THESIS_TYPE,
    build_thesis,
    thesis_section_keys,
)
from tests.fixtures.steps import (
    FakeLLM,
    FakeRetriever,
    make_all_items_corpus,
    valid_section_json,
)

DOSSIER_ITEMS = {"ITEM 1", "ITEM 1A", "ITEM 5", "ITEM 7", "ITEM 8"}

EXPECTED_KEYS = [
    "hold",
    "why",
    "assumptions",
    "triggers",
    "devils_advocate",
    "gaps",
]


def make_generator(corpus=None, llm=None, years=(2025,)):
    retriever = (
        FakeRetriever(corpus, years=years)
        if corpus is not None
        else FakeRetriever(make_all_items_corpus())
    )
    return ArtifactGenerator(retriever, llm or FakeLLM(valid_section_json()))


class TestThesisSections:
    def test_thesis_drafts_all_sections_in_order(self):
        artifact = build_thesis(make_generator(), "TSLA")
        assert artifact.artifact_type == THESIS_TYPE
        assert artifact.ticker == "TSLA"
        assert artifact.fiscal_year == 2025
        assert [s.key for s in artifact.sections] == EXPECTED_KEYS

    def test_every_thesis_section_is_grounded(self):
        artifact = build_thesis(make_generator(), "TSLA")
        for section in artifact.sections:
            assert section.content
            assert len(section.sources) >= 1
            assert section.evidence

    def test_thesis_scopes_to_the_dossier_items(self):
        requested = set(item for spec in THESIS_SECTIONS for item in spec.items)
        assert requested == DOSSIER_ITEMS
        artifact = build_thesis(make_generator(), "TSLA")
        assert set(artifact.scope.items) == DOSSIER_ITEMS

    def test_section_keys_are_stable_and_unique(self):
        keys = thesis_section_keys()
        assert keys == EXPECTED_KEYS
        assert len(keys) == len(set(keys))
        assert all(s.key in keys for s in THESIS_SECTIONS)

    def test_devils_advocate_spec_argues_against_the_position(self):
        devils = next(s for s in THESIS_SECTIONS if s.key == "devils_advocate")
        assert "against" in devils.query.lower() or "opposite" in devils.query.lower()
        assert "against" in devils.instruction.lower()


class TestBuildThesis:
    def test_build_thesis_round_trips_through_the_draft_store_shape(self):
        artifact = build_thesis(make_generator(), "TSLA")
        dumped = artifact.model_dump()
        assert dumped["artifact_type"] == THESIS_TYPE
        assert [s["key"] for s in dumped["sections"]] == EXPECTED_KEYS

    def test_build_thesis_uses_the_latest_complete_year(self):
        corpus = [
            *make_all_items_corpus(year=2026),
            *make_all_items_corpus(year=2025),
        ]
        artifact = build_thesis(make_generator(corpus=corpus, years=(2026, 2025)), "TSLA")
        assert artifact.fiscal_year == 2026

    def test_no_source_corpus_raises_no_source_error(self):
        generator = make_generator(corpus=[], )
        with pytest.raises(Exception):
            build_thesis(generator, "TSLA")


class TestThesisStore:
    def test_get_missing_returns_none(self, tmp_path):
        store = ThesisStore(str(tmp_path / "steps.db"))
        assert store.get("a@example.com", "TSLA") is None

    def test_save_and_get_round_trip(self, tmp_path):
        store = ThesisStore(str(tmp_path / "steps.db"))
        saved = store.save("a@example.com", "TSLA", {"hold": "I hold TSLA."})
        assert saved["content"]["hold"] == "I hold TSLA."
        assert saved["saved_at"]
        doc = store.get("a@example.com", "TSLA")
        assert doc["content"] == {"hold": "I hold TSLA."}
        assert doc["saved_at"] == saved["saved_at"]

    def test_thesis_is_scoped_to_user_and_ticker(self, tmp_path):
        store = ThesisStore(str(tmp_path / "steps.db"))
        store.save("a@example.com", "TSLA", {"hold": "a thesis"})
        assert store.get("b@example.com", "TSLA") is None
        assert store.get("a@example.com", "MSFT") is None
        assert store.get("a@example.com", "TSLA") is not None

    def test_save_overwrites_and_stamps_a_new_saved_at(self, tmp_path):
        store = ThesisStore(str(tmp_path / "steps.db"))
        first = store.save("a@example.com", "TSLA", {"hold": "v1"})
        second = store.save("a@example.com", "TSLA", {"hold": "v2", "why": "because"})
        assert second["saved_at"] >= first["saved_at"]
        doc = store.get("a@example.com", "TSLA")
        assert doc["content"] == {"hold": "v2", "why": "because"}
