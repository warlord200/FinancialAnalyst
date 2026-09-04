"""The T13 eval CLI.

Runs the retrieval-quality gate and writes the dashboard snapshot the web
app serves (``storage/evals/dashboard.json``). Three subcommands, one per
eval mode:

    python -m financial_analyst.evaluation.cli curated
        The hand-curated Tesla analyst benchmark, scored per dossier step
        over the live TSLA index. Needs the configured embedder.

    python -m financial_analyst.evaluation.cli regression
        The synthetic QA datasets, re-measured and compared to their
        recorded baselines (continuity). Reuses cached scratch corpora.

    python -m financial_analyst.evaluation.cli smoke --ticker AAPL
        The automated per-company smoke gate (coverage + self-retrieval).

Running the heavy modes requires Cloudflare credentials and network
access to embed queries; the offline pytest suite covers every scoring
path with mocked embedders instead.
"""

import argparse
import sys
from pathlib import Path

from financial_analyst.evaluation.benchmarks import (
    CURATED_BENCHMARK_PATH,
    load_curated_benchmark,
)
from financial_analyst.evaluation.corpus import snapshot
from financial_analyst.evaluation.report import (
    DEFAULT_BASELINES_PATH,
    DEFAULT_DASHBOARD_PATH,
    attach_continuity,
    load_baselines,
    load_dashboard,
    update_dashboard,
)
from financial_analyst.evaluation.runner import run_curated_benchmark, scoped_retrieve
from financial_analyst.evaluation.smoke import run_smoke


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="financial_analyst.evaluation.cli",
        description="Retrieval-quality eval harness (T13).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    curated = sub.add_parser("curated", help="run the curated Tesla benchmark")
    curated.add_argument("--ticker", default="TSLA")
    curated.add_argument("--top-k", type=int, default=None)
    curated.add_argument("--benchmark", default=str(CURATED_BENCHMARK_PATH))

    regression = sub.add_parser("regression", help="run the synthetic regression sets")
    regression.add_argument("--data-dir", default="storage/evals")
    regression.add_argument(
        "--work-dir", default="storage/evals/chroma_hybrid",
        help="dir holding the cached re-embedded dataset corpora",
    )
    regression.add_argument("--configs", default="vector,hybrid")
    regression.add_argument("--top-k", type=int, default=4)
    regression.add_argument("--rebuild", action="store_true")
    regression.add_argument(
        "--tolerance", type=float, default=0.02,
        help="absolute metric drop that counts as a regression",
    )
    regression.add_argument(
        "--no-fail", action="store_true",
        help="report regressions without exiting non-zero",
    )

    smoke = sub.add_parser("smoke", help="run the per-company smoke eval")
    smoke.add_argument("--ticker", required=True)
    smoke.add_argument("--samples", type=int, default=3)
    smoke.add_argument("--hit-floor", type=float, default=1.0)
    smoke.add_argument("--seed", type=int, default=0)

    for p in (curated, regression, smoke):
        p.add_argument("--dashboard", default=DEFAULT_DASHBOARD_PATH)
    return parser


def _print_per_step(table_rows: list[dict], columns) -> None:
    header = "  ".join(columns)
    print(header)
    for row in table_rows:
        print("  ".join(str(row.get(col, "")) for col in columns))


def _fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _ensure_runtime(use_reranker: bool = False):
    """Set up the hosted embed model and an optional reranker.

    Every eval mode measures retrieval the same way the app serves it: the
    single embed model on Cloudflare (no local model loaded) and, when
    ``RERANKER_MODEL`` is set, the cross-encoder on top. Missing Cloudflare
    credentials raise so the operator is told why the heavy modes cannot
    run.
    """
    from llama_index.core import Settings

    from financial_analyst import config
    from financial_analyst.steps.retrieval import (
        CloudflareEmbedding,
        EMBED_QUERY_INSTRUCTION,
        reranker_from_env,
    )

    account_id, api_token = config.get_cloudflare_credentials()
    if not account_id or not api_token:
        raise SystemExit(
            "Cloudflare Workers AI is not configured: set CLOUDFLARE_ACCOUNT_ID "
            "and CLOUDFLARE_API_TOKEN in .env to embed eval queries"
        )
    Settings.embed_model = CloudflareEmbedding(
        account_id=account_id,
        api_key=api_token,
        query_instruction=EMBED_QUERY_INSTRUCTION,
        embed_batch_size=32,
    )
    return reranker_from_env() if use_reranker else None


def _live_retriever(use_reranker: bool = False):
    from financial_analyst.indexing.company_index import CompanyIndex
    from financial_analyst.steps.retrieval import ScopedRetriever

    reranker = _ensure_runtime(use_reranker)
    return ScopedRetriever(
        CompanyIndex(chroma_path="./chroma_db", storage_base="./storage"),
        reranker=reranker,
    )


def cmd_curated(args) -> int:
    retriever = _live_retriever(use_reranker=False)
    benchmark = load_curated_benchmark(args.benchmark)
    retrieve = lambda question: scoped_retrieve(
        retriever, args.ticker, question, top_k=args.top_k
    )
    result = run_curated_benchmark(benchmark, retrieve)
    print(
        f"Curated benchmark {benchmark.name} on {benchmark.ticker}: "
        f"{len(benchmark.questions)} questions, top_k={result['top_k']}"
    )
    rows = []
    for step in ("2", "3", "4", "search_all"):
        agg = result["per_step"][step]
        if agg["num_queries"] == 0:
            continue
        rows.append(
            {
                "step": step,
                "queries": agg["num_queries"],
                "mrr": _fmt(agg["mrr"]),
                "hit_rate": _fmt(agg["hit_rate"]),
                "ndcg": _fmt(agg["ndcg"]),
            }
        )
    _print_per_step(rows, ["step", "queries", "mrr", "hit_rate", "ndcg"])
    update_dashboard(args.dashboard, "curated", [{**result, "config": "hybrid"}])
    return 0


def cmd_regression(args) -> int:
    import os
    from llama_index.core import Settings

    from financial_analyst.evaluation.eval_utils import EmbeddingQAFinetuneDataset
    from financial_analyst.evaluation.regression import (
        current_embed_model_name,
        ensure_eval_collection,
        evaluate_dataset,
        scoped_dataset_retrieve,
    )
    from financial_analyst.indexing.company_index import CompanyIndex
    from financial_analyst.steps.retrieval import CrossEncoderReranker, ScopedRetriever

    _ensure_runtime()
    index = CompanyIndex(
        chroma_path=args.work_dir, storage_base=str(Path(args.work_dir) / "storage")
    )
    dataset_dirs = sorted(
        p for p in Path(args.data_dir).iterdir() if (p / "train_dataset.json").is_file()
    )
    if not dataset_dirs:
        print(f"No QA datasets under {args.data_dir}")
        return 1

    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    baselines = load_baselines(DEFAULT_BASELINES_PATH)["datasets"]
    rows = []
    regressions = False

    for label_dir in dataset_dirs:
        label = label_dir.name
        dataset = EmbeddingQAFinetuneDataset.from_json(
            str(label_dir / "train_dataset.json")
        )
        if ensure_eval_collection(
            index, label, dataset, args.rebuild, current_embed_model_name()
        ):
            print(f"Embedded corpus for {label} ({len(dataset.corpus)} chunks)")
        for config in configs:
            if config == "vector":
                retriever = ScopedRetriever(index, use_hybrid=False)
            elif config == "hybrid":
                retriever = ScopedRetriever(index, use_hybrid=True)
            elif config == "rerank":
                model = os.getenv("RERANKER_MODEL", "").strip()
                if not model:
                    print(f"Skipping rerank for {label}: RERANKER_MODEL not set")
                    continue
                retriever = ScopedRetriever(
                    index, use_hybrid=True, reranker=CrossEncoderReranker(model)
                )
            else:
                print(f"Unknown config: {config}")
                return 1

            out = evaluate_dataset(
                dataset, scoped_dataset_retrieve(retriever, label), top_k=args.top_k
            )
            summary = {
                "num_queries": out["num_queries"],
                "mrr": out["mrr"],
                "hit_rate": out["hit_rate"],
                "ndcg": out["ndcg"],
            }
            baseline = (baselines.get(label) or {}).get(config)
            row = attach_continuity(
                summary,
                baseline,
                dataset=label,
                config=config,
                tolerance=args.tolerance,
            )
            rows.append(row)
            if row["regressed"]:
                regressions = True
            print(
                f"[{config}] {label}: {row['num_queries']} queries | "
                f"mrr {_fmt(row['mrr'])} (base {_fmt(row['baseline_mrr'])}) | "
                f"hit {_fmt(row['hit_rate'])} | ndcg {_fmt(row['ndcg'])}"
                + ("  REGRESSION" if row["regressed"] else "")
            )

    update_dashboard(args.dashboard, "regression", rows)
    if regressions and not args.no_fail:
        print("REGRESSION: one or more metrics fell past tolerance")
        return 1
    return 0


def cmd_smoke(args) -> int:
    retriever = _live_retriever(use_reranker=False)
    chunks = snapshot(retriever.index, args.ticker)
    if not chunks:
        print(f"No ingested corpus for {args.ticker}; ingest it first")
        return 1

    def retrieve(query, items):
        return retriever.retrieve(args.ticker, query, items=items, top_k=4)

    out = run_smoke(
        args.ticker,
        chunks,
        retrieve,
        samples_per_step=args.samples,
        hit_floor=args.hit_floor,
        seed=args.seed,
    )
    print(f"Smoke eval for {out['ticker']}: {'PASS' if out['passed'] else 'FAIL'}")
    for step, step_out in out["steps"].items():
        if step_out.get("skipped"):
            print(f"  step {step}: skipped ({', '.join(out['checks'][step]['items_missing'])})")
        else:
            print(
                f"  step {step}: {step_out['samples']} samples | "
                f"hit {_fmt(step_out['retrieval_hit_rate'])} | "
                f"in-scope {_fmt(step_out['in_scope_rate'])}"
            )

    existing = load_dashboard(args.dashboard) or {}
    entries = [
        e for e in existing.get("smoke", []) if e.get("ticker") != out["ticker"]
    ]
    entries.append(out)
    update_dashboard(args.dashboard, "smoke", entries[-20:])
    return 0 if out["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "curated":
        return cmd_curated(args)
    if args.command == "regression":
        return cmd_regression(args)
    if args.command == "smoke":
        return cmd_smoke(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
