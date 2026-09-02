"""Retrieval-quality eval comparing vector, hybrid BM25, and reranked retrieval.

Manual eval script — not part of the routine pytest suite. It loads real
embedding and reranker models, so the heavy work only runs when the module
is executed directly:

    python tests/test_llamaindex_agent.py --limit 40

It reuses the QA datasets in storage/evals (one per company), re-embeds
each corpus with the configured embed model (``BAAI/bge-m3`` by default,
which runs on CPU), and measures three retrieval configs per company:

  - ``vector`` — pure dense retrieval (the baseline)
  - ``hybrid`` — dense + BM25 keyword search fused by reciprocal rank fusion
  - ``rerank``  — hybrid, then a cross-encoder reranker
    (``BAAI/bge-reranker-v2-m3``)

Because the corpus is re-embedded with the configured model, no GPU is
required and every config is measured in the same harness on the same
corpus. The numbers (README "METRICS") are the vector/hybrid/rerank
comparison this ticket reports. The ad-hoc eval harness that replaces this
script is T13.
"""

import argparse
import json
import random
from pathlib import Path

METRICS = ["mrr", "hit_rate", "ndcg"]


def _norm(text: str) -> str:
    return " ".join(text.split())


def _limited(dataset, limit, seed):
    if limit is None or limit >= len(dataset.queries):
        return dataset
    ids = list(dataset.queries)
    rng = random.Random(seed)
    rng.shuffle(ids)
    chosen = ids[:limit]
    return dataset.__class__(
        queries={i: dataset.queries[i] for i in chosen},
        corpus=dataset.corpus,
        relevant_docs={i: dataset.relevant_docs[i] for i in chosen},
    )


def _mean(values) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _ensure_collection(index, label, dataset, rebuild, embed_model_name) -> bool:
    """Build the eval collection for a company if missing or stale.

    Returns True if a build happened, False if the existing collection was
    reused (chunks are cached in ``--work-dir`` so repeated runs skip the
    expensive re-embedding step). Reuse is only allowed when the stored
    collection was embedded with the same model — otherwise the vectors
    silently belong to a different model than the one being reported.
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
    from llama_index.core.schema import TextNode

    nodes = [
        TextNode(id_=node_id, text=text, metadata={"ticker": label})
        for node_id, text in dataset.corpus.items()
    ]
    index.build(label, nodes)
    return True


def main() -> None:
    from llama_index.core import Settings
    from llama_index.core.base.base_retriever import BaseRetriever
    from llama_index.core.evaluation import (
        BaseRetrievalEvaluator,
        RetrieverEvaluator,
    )
    from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    import torch

    from financial_analyst.evaluation.eval_utils import (
        EmbeddingQAFinetuneDataset,
        display_results,
        evaluate_dataset,
    )
    from financial_analyst.indexing.company_index import CompanyIndex
    from financial_analyst.steps.retrieval import (
        CrossEncoderReranker,
        ScopedRetriever,
    )

    class ScopedRetrieverAdapter(BaseRetriever):
        """Wrap ScopedRetriever for the RetrieverEvaluator.

        ScopedRetriever returns SourceChunks (text + metadata); the QA
        datasets are keyed by corpus ids, so retrieved chunk texts are
        mapped back to their corpus ids by whitespace-normalized text match.
        """

        def __init__(
            self, scoped_retriever, ticker, top_k, corpus_id_by_text, corpus
        ):
            super().__init__()
            self.scoped_retriever = scoped_retriever
            self.ticker = ticker
            self.top_k = top_k
            self.corpus_id_by_text = corpus_id_by_text
            self.corpus = corpus

        def _retrieve(self, query_bundle):
            if not isinstance(query_bundle, QueryBundle):
                query_bundle = QueryBundle(str(query_bundle))
            chunks = self.scoped_retriever.retrieve(
                self.ticker, query_bundle.query_str, top_k=self.top_k
            )
            nodes = []
            for chunk in chunks:
                corpus_id = self.corpus_id_by_text.get(_norm(chunk.text))
                if corpus_id is not None:
                    nodes.append(
                        NodeWithScore(
                            node=TextNode(
                                id_=corpus_id, text=self.corpus[corpus_id]
                            ),
                            score=1.0,
                        )
                    )
            return nodes

    # Monkey-patch the deprecated evaluate_dataset onto the evaluator: the
    # upstream implementation was removed in April 2026, so eval_utils.py
    # re-implements it and we inject it here (see eval_utils.py / README P4).
    BaseRetrievalEvaluator.evaluate_dataset = evaluate_dataset  # type: ignore

    args = _parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}, embed model: {args.embed_model}")
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=args.embed_model, device=device, embed_batch_size=32
    )

    dataset_dirs = sorted(
        p for p in Path(args.data_dir).iterdir() if (p / "train_dataset.json").is_file()
    )
    if not dataset_dirs:
        raise SystemExit(f"No QA datasets under {args.data_dir}")

    index = CompanyIndex(
        chroma_path=args.work_dir, storage_base=str(Path(args.work_dir) / "storage")
    )
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    summary: dict = {}

    for label_dir in dataset_dirs:
        label = label_dir.name
        dataset = EmbeddingQAFinetuneDataset.from_json(
            str(label_dir / "train_dataset.json")
        )
        corpus_id_by_text = {_norm(text): nid for nid, text in dataset.corpus.items()}
        if _ensure_collection(
            index, label, dataset, args.rebuild, args.embed_model
        ):
            print(f"Built corpus for {label} ({len(dataset.corpus)} chunks)")
        sub = _limited(dataset, args.limit, args.seed)

        for config in configs:
            if config == "vector":
                retriever = ScopedRetriever(index, use_hybrid=False)
            elif config == "hybrid":
                retriever = ScopedRetriever(index, use_hybrid=True)
            elif config == "rerank":
                retriever = ScopedRetriever(
                    index,
                    use_hybrid=True,
                    reranker=CrossEncoderReranker(args.reranker_model),
                )
            else:
                raise SystemExit(f"Unknown config: {config}")

            adapter = ScopedRetrieverAdapter(
                retriever, label, args.top_k, corpus_id_by_text, dataset.corpus
            )
            evaluator = RetrieverEvaluator.from_metric_names(
                METRICS, retriever=adapter
            )
            print(f"[{config}] evaluating {label} on {len(sub.queries)} queries...")
            results = evaluator.evaluate_dataset(sub, show_progress=True)  # type: ignore
            metric_dicts = [r.metric_vals_dict for r in results]
            means = {
                metric: _mean([d.get(metric) for d in metric_dicts])
                for metric in METRICS
            }
            summary.setdefault(config, {})[label] = {
                "num_queries": len(metric_dicts),
                **means,
            }
            display_results(f"{config} | {label}", results, METRICS)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))
    print(f"Saved summary to {out}")

    print("\nAGGREGATE (mean over companies, weighted by query count)")
    for config, per_company in summary.items():
        total = sum(v["num_queries"] for v in per_company.values())
        weighted = {
            metric: (
                sum(
                    v[metric] * v["num_queries"]
                    for v in per_company.values()
                    if v[metric] is not None
                )
                / total
                if total
                else None
            )
            for metric in METRICS
        }
        print(f"{config:8s} {weighted}")


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", default="storage/evals", help="dir containing QA datasets"
    )
    parser.add_argument(
        "--work-dir",
        default="storage/evals/chroma_hybrid",
        help="dir for the re-embedded Chroma collections",
    )
    parser.add_argument("--embed-model", default="BAAI/bge-m3")
    parser.add_argument(
        "--reranker-model", default="BAAI/bge-reranker-v2-m3"
    )
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="max queries per company (all when unset)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--configs", default="vector,hybrid,rerank"
    )
    parser.add_argument("--out", default="storage/evals/hybrid_summary.json")
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
