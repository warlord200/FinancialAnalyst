"""The synthetic regression eval mode.

These are the two pre-existing QA datasets (``storage/evals/*``), one per
company, whose questions were machine-generated from the company's own
filing chunks. They predate the curated benchmark and serve as the
continuity check: the same corpus, re-measured on every run, so a change
to retrieval, the embedder, or chunking that quietly hurts quality shows up
as a metric drift against the recorded baseline (``report.py`` compares
and the CLI reports any regression).

Each dataset embeds its own corpus (the corpus text lives in the dataset
file, independent of the live index) into a scratch Chroma collection whose
recorded ``embed_model`` identity gates reuse — a collection embedded by a
different model is rebuilt, never scored. Scoring mirrors the curated
runner: retrieval results are ranked and matched against each query's
relevant corpus ids; the aggregate per (dataset, config) is what the
continuity check compares.
"""

from typing import Callable, Sequence

from llama_index.core import Settings
from llama_index.core.schema import TextNode

from financial_analyst.evaluation.benchmarks import normalize
from financial_analyst.evaluation.eval_utils import EmbeddingQAFinetuneDataset
from financial_analyst.evaluation.metrics import aggregate, query_metrics


def corpus_id_by_text(corpus: dict[str, str]) -> dict[str, str]:
    """Map whitespace-normalized corpus text back to its corpus id.

    Retrieval returns chunk text; the QA dataset keys relevance by corpus
    id, so every result is resolved through this map (as the legacy harness
    did) before ranking.
    """
    return {normalize(text): node_id for node_id, text in corpus.items()}


def ensure_eval_collection(
    index,
    label: str,
    dataset: EmbeddingQAFinetuneDataset,
    rebuild: bool = False,
    embed_model_name: str | None = None,
) -> bool:
    """Build (or rebuild) the scratch Chroma collection for a dataset.

    Returns True when a build happened and False when an existing
    collection was reused. Reuse is only allowed when the stored collection
    was embedded by the same model (``embed_model_name`` empty means the
    caller does not care), matching the legacy harness so a model change
    never silently scores a stale corpus.
    """
    import chromadb

    try:
        collection = index.collection(label)
        recorded = (collection.metadata or {}).get("embed_model")
        if not rebuild and collection.count() == len(dataset.corpus):
            if not embed_model_name or recorded == embed_model_name:
                return False
    except chromadb.errors.NotFoundError:
        pass

    nodes = [
        TextNode(id_=node_id, text=text, metadata={"ticker": label})
        for node_id, text in dataset.corpus.items()
    ]
    index.build(label, nodes)
    return True


def scoped_dataset_retrieve(retriever, label: str):
    """Bind a retriever to a dataset's scratch collection.

    The dataset's corpus lives under its own collection (named by the
    dataset label), so retrieving against it is a normal scoped retrieval
    on that label. The returned callable takes a query and returns the
    ranked :class:`SourceChunk` objects ``evaluate_dataset`` scores.
    """

    def retrieve(query: str):
        return retriever.retrieve(label, query)

    return retrieve


def evaluate_dataset(
    dataset: EmbeddingQAFinetuneDataset,
    retrieve: Callable[[str], Sequence],
    top_k: int = 4,
) -> dict:
    """Score every query in a QA dataset and aggregate the metrics.

    ``retrieve(query)`` returns the ranked chunks for one query. Results
    whose text is not in the dataset corpus are dropped (they cannot be
    scored), and duplicate results are de-duplicated before ranking so one
    chunk never inflates NDCG.
    """
    ids_by_text = corpus_id_by_text(dataset.corpus)
    rows = []
    for query_id, query in dataset.queries.items():
        expected = set(dataset.relevant_docs.get(query_id, []))
        ranked: list[str] = []
        for chunk in list(retrieve(query))[:top_k]:
            corpus_id = ids_by_text.get(normalize(chunk.text))
            if corpus_id is not None and corpus_id not in ranked:
                ranked.append(corpus_id)
        gains = [corpus_id in expected for corpus_id in ranked]
        metrics = query_metrics(gains, k=top_k, expected_positives=len(expected))
        rows.append(
            {
                "question_id": query_id,
                "retrieved": len(ranked),
                "matched": sum(1 for g in gains if g),
                **metrics,
            }
        )
    summary = aggregate(rows)
    return {**summary, "per_query": rows}


def current_embed_model_name() -> str:
    """The recorded identity the scratch collections are keyed on."""
    model = getattr(Settings, "embed_model", None)
    return getattr(model, "model_name", "") or ""
