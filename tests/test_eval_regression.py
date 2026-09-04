"""Unit tests for the synthetic regression runner (``regression.py``).

The regression mode measures the pre-existing synthetic QA datasets (one
per company) and reports whether retrieval quality has drifted from its
recorded baseline. Like the curated runner, the scoring core takes a
``retrieve`` callable so these tests stay offline; an integration test then
checks the wiring against a real scratch index with a scripted dense leg.
"""

import math

import pytest
from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM

from financial_analyst.evaluation.eval_utils import EmbeddingQAFinetuneDataset
from financial_analyst.evaluation.benchmarks import normalize
from financial_analyst.evaluation.regression import (
    corpus_id_by_text,
    ensure_eval_collection,
    evaluate_dataset,
    scoped_dataset_retrieve,
)
from financial_analyst.steps.retrieval import SourceChunk

CORPUS = {
    "c1": "Revenue grew 10% in fiscal 2025 driven by energy storage.",
    "c2": "The company designs and sells electric vehicles.",
    "c3": "We face competition from other automakers.",
}


def make_dataset(queries=None):
    queries = queries or {
        "q1": "How did revenue move in fiscal 2025?",
        "q2": "What does the company build?",
        "q3": "Who competes with the company?",
    }
    return EmbeddingQAFinetuneDataset(
        queries=queries,
        corpus=CORPUS,
        relevant_docs={"q1": ["c1"], "q2": ["c2"], "q3": ["c3"]},
        mode="text",
    )


def cchunk(corpus_id):
    return SourceChunk(text=CORPUS[corpus_id], ticker="D")


class TestCorpusIdByText:
    def test_maps_normalized_text_to_id(self):
        ids = corpus_id_by_text(CORPUS)
        assert ids["revenue grew 10% in fiscal 2025 driven by energy storage."] == "c1"
        # A different whitespace layout normalises to the same key.
        key = "  revenue grew  10% in fiscal 2025 driven by energy storage."
        assert normalize(key) in ids
        assert ids[normalize(key)] == "c1"


class TestEvaluateDataset:
    def test_scores_ranked_results_against_relevant_ids(self):
        dataset = make_dataset()

        def retrieve(query):
            if query.startswith("How did revenue"):
                return [cchunk("c3"), cchunk("c1")]
            if query.startswith("What does"):
                return [cchunk("c2")]
            return []

        out = evaluate_dataset(dataset, retrieve)
        rows = {r["question_id"]: r for r in out["per_query"]}
        assert rows["q1"]["mrr"] == pytest.approx(0.5)
        assert rows["q1"]["hit_rate"] == 1.0
        assert rows["q1"]["matched"] == 1
        assert rows["q2"]["hit_rate"] == 1.0
        assert rows["q2"]["mrr"] == 1.0
        assert rows["q3"]["hit_rate"] == 0.0
        assert out["num_queries"] == 3
        assert out["mrr"] == pytest.approx(0.5)
        assert out["hit_rate"] == pytest.approx(2 / 3)

    def test_duplicate_retrieved_ids_count_once(self):
        dataset = make_dataset()

        def retrieve(query):
            return [cchunk("c1"), cchunk("c1")]

        out = evaluate_dataset(dataset, retrieve)
        row = out["per_query"][0]
        assert row["matched"] == 1
        assert row["retrieved"] == 1

    def test_retrieval_results_not_in_the_corpus_are_dropped(self):
        dataset = make_dataset()

        def retrieve(query):
            return [
                SourceChunk(text="This text is not in the corpus at all.", ticker="D"),
                cchunk("c1"),
            ]

        out = evaluate_dataset(dataset, retrieve)
        row = out["per_query"][0]
        assert row["retrieved"] == 1
        assert row["matched"] == 1


# --- Integration: wiring against a real scratch index ------------------------


@pytest.fixture
def mock_models():
    old_embed, old_llm = Settings._embed_model, Settings._llm
    Settings.embed_model = MockEmbedding(embed_dim=8)
    Settings.llm = MockLLM()
    try:
        yield
    finally:
        Settings._embed_model = old_embed
        Settings._llm = old_llm


def build_scratch_index(tmp_path, dataset):
    from llama_index.core.schema import TextNode

    from financial_analyst.indexing.company_index import CompanyIndex

    nodes = [
        TextNode(id_=node_id, text=text, metadata={"ticker": "D"})
        for node_id, text in dataset.corpus.items()
    ]
    index = CompanyIndex(
        chroma_path=str(tmp_path / "chroma"), storage_base=str(tmp_path / "storage")
    )
    index.build("2026_Tesla", nodes)
    return index


class TestEvalCollectionWiring:
    def test_build_records_the_embed_model_identity(self, tmp_path, mock_models):
        dataset = make_dataset()
        index = build_scratch_index(tmp_path, dataset)
        collection = index.collection("2026_Tesla")
        assert collection.count() == len(dataset.corpus)
        assert collection.metadata["embed_model"] == "unknown"

    def test_ensure_rebuilds_when_the_embed_model_differs(self, tmp_path, mock_models):
        dataset = make_dataset()
        index = build_scratch_index(tmp_path, dataset)
        assert (
            ensure_eval_collection(index, "2026_Tesla", dataset, embed_model_name="other")
            is True
        )

    def test_scoped_dataset_retrieve_feeds_evaluate_dataset(
        self, tmp_path, mock_models, monkeypatch
    ):
        from financial_analyst.steps.retrieval import ScopedRetriever

        dataset = make_dataset()
        index = build_scratch_index(tmp_path, dataset)
        retriever = ScopedRetriever(index)

        def dense_everything(collection, query_embedding, where, n, ticker):
            return [cchunk(cid) for cid in ("c1", "c2", "c3")]

        monkeypatch.setattr(retriever, "_query_dense", dense_everything)
        monkeypatch.setattr(retriever, "_query_sparse", lambda *a, **k: [])

        retrieve = scoped_dataset_retrieve(retriever, "2026_Tesla")
        out = evaluate_dataset(dataset, lambda q: retrieve(q))
        assert out["num_queries"] == 3
        rows = {r["question_id"]: r for r in out["per_query"]}
        # The dense leg always returns c1, c2, c3 in that order.
        assert rows["q1"]["mrr"] == pytest.approx(1.0)
        assert rows["q2"]["mrr"] == pytest.approx(0.5)
        assert rows["q3"]["mrr"] == pytest.approx(1 / 3)
        assert out["hit_rate"] == pytest.approx(1.0)
        # NDCG@k discounts by rank: dcg = 1/log2(rank+1), idcg = 1.
        ndcg_expected = (1 + 1 / math.log2(3) + 1 / math.log2(4)) / 3
        assert out["ndcg"] == pytest.approx(ndcg_expected)
