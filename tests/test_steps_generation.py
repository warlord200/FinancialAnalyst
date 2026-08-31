import json

import pytest

from financial_analyst.steps.business_swot import BUSINESS_SWOT_SECTIONS
from financial_analyst.steps.generation import (
    ArtifactGenerator,
    ArtifactValidationError,
    NoSourceError,
    SectionSpec,
)
from tests.fixtures.steps import FakeLLM, FakeRetriever, ITEM_1_TEXT, valid_section_json

SINGLE_SPEC = SectionSpec(
    key="overview",
    heading="Business Overview",
    query="What does the company do?",
)

TWO_SPECS = [
    SectionSpec(key="a", heading="Alpha Section", query="First query."),
    SectionSpec(
        key="b",
        heading="Beta Section",
        query="Second query.",
        context_from=("a",),
    ),
]


def no_sources_json():
    return json.dumps(
        {
            "content": "Tesla designs and manufactures electric vehicles and energy storage products.",
            "evidence": ["Tesla designs and manufactures electric vehicles and energy storage products."],
        }
    )


def fabricated_evidence_json():
    return json.dumps(
        {
            "content": "The company does something.",
            "source_refs": [1],
            "evidence": ["This sentence is not in the source material at all."],
        }
    )


def bad_ref_json():
    return json.dumps(
        {
            "content": "Tesla designs and manufactures electric vehicles.",
            "source_refs": [7],
            "evidence": ["Tesla designs and manufactures electric vehicles."],
        }
    )


def make_generator(retriever=None, llm=None):
    retriever = retriever or FakeRetriever()
    return ArtifactGenerator(retriever, llm or FakeLLM())


class TestFramework:
    def test_generate_returns_artifact_with_source_tags(self):
        generator = make_generator()
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert artifact.artifact_type == "test_artifact"
        assert artifact.fiscal_year == 2025
        assert artifact.scope.items == ["ITEM 1", "ITEM 1A"]
        assert len(artifact.sections) == 1
        section = artifact.sections[0]
        assert section.key == "overview"
        assert section.heading == "Business Overview"
        assert section.content
        assert len(section.sources) >= 1
        assert section.evidence

    def test_generate_assigns_heading_from_spec_not_llm(self):
        generator = make_generator()
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert artifact.sections[0].heading == "Business Overview"

    def test_generate_derives_source_tags_from_cited_passage(self):
        generator = make_generator()
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        sources = artifact.sections[0].sources
        assert ("item", "ITEM 1") in [(t.type, t.value) for t in sources]
        assert ("fiscal_year", "2025") in [(t.type, t.value) for t in sources]
        assert all(t.value != "1A" for t in sources)

    def test_generate_accepts_string_number_refs(self):
        llm = FakeLLM(valid_section_json(refs=["1"]))
        generator = make_generator(llm=llm)
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert artifact.sections[0].sources

    def test_generate_rejects_section_without_sources(self):
        generator = make_generator(llm=FakeLLM(no_sources_json(), no_sources_json()))
        with pytest.raises(ArtifactValidationError) as exc:
            generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert "cites no source passages" in str(exc.value)

    def test_generate_rejects_fabricated_evidence(self):
        generator = make_generator(llm=FakeLLM(fabricated_evidence_json()))
        with pytest.raises(ArtifactValidationError) as exc:
            generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert "evidence not found verbatim" in str(exc.value)

    def test_generate_rejects_source_ref_not_in_corpus(self):
        generator = make_generator(llm=FakeLLM(bad_ref_json()))
        with pytest.raises(ArtifactValidationError) as exc:
            generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert "not among the passages shown: 7" in str(exc.value)

    def test_generate_accepts_markdown_fenced_json(self):
        fenced = f"```json\n{valid_section_json()}\n```"
        generator = make_generator(llm=FakeLLM(fenced))
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert artifact.sections[0].content

    def test_generate_accepts_json_with_leading_prose(self):
        wrapped = f"Here is the section:\n{valid_section_json()}"
        generator = make_generator(llm=FakeLLM(wrapped))
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert artifact.sections[0].content

    def test_generate_retries_with_repair_prompt(self):
        llm = FakeLLM(fabricated_evidence_json(), valid_section_json())
        generator = make_generator(llm=llm)
        artifact = generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])
        assert len(artifact.sections) == 1
        assert llm.calls == 2
        assert len(llm.prompts) == 2
        assert llm.prompts[1] != llm.prompts[0]
        assert "rejected" in llm.prompts[1]

    def test_generate_raises_no_source_when_ticker_not_ingested(self):
        generator = make_generator(retriever=FakeRetriever(chunks=[], years=[]))
        with pytest.raises(NoSourceError):
            generator.generate("NOPE", "test_artifact", [SINGLE_SPEC])

    def test_generate_raises_no_source_when_no_chunks_for_section(self):
        generator = make_generator(retriever=FakeRetriever(chunks=[], years=[2025]))
        with pytest.raises(NoSourceError):
            generator.generate("TSLA", "test_artifact", [SINGLE_SPEC])

    def test_context_from_includes_prior_sections(self):
        llm = FakeLLM()
        generator = make_generator(llm=llm)
        generator.generate("TSLA", "test_artifact", TWO_SPECS)
        assert len(llm.prompts) == 2
        assert "Alpha Section" in llm.prompts[1]
        assert "Alpha Section" in llm.prompts[0]


class TestBusinessSwotSpec:
    def test_business_swot_builds_all_sections_in_order(self):
        generator = make_generator()
        artifact = generator.generate("TSLA", "business_swot", BUSINESS_SWOT_SECTIONS)
        keys = [s.key for s in artifact.sections]
        assert keys == [
            "overview",
            "segments",
            "revenue_model",
            "customers",
            "suppliers",
            "regulators",
            "management",
            "swot_strengths",
            "swot_weaknesses",
            "swot_opportunities",
            "swot_threats",
        ]
        assert artifact.sections[0].heading == "Business Overview"
        for section in artifact.sections:
            assert section.content
            assert len(section.sources) >= 1
            assert section.evidence
        swot = [s for s in artifact.sections if s.key.startswith("swot_")]
        assert len(swot) == 4
        assert {s.key for s in swot} == {
            "swot_strengths",
            "swot_weaknesses",
            "swot_opportunities",
            "swot_threats",
        }

    def test_swot_sections_receive_earlier_context(self):
        llm = FakeLLM()
        generator = make_generator(llm=llm)
        generator.generate("TSLA", "business_swot", BUSINESS_SWOT_SECTIONS)
        for spec, prompt in zip(BUSINESS_SWOT_SECTIONS, llm.prompts):
            if not spec.key.startswith("swot_"):
                continue
            for dep in spec.context_from:
                dep_heading = next(s.heading for s in BUSINESS_SWOT_SECTIONS if s.key == dep)
                assert dep_heading in prompt
