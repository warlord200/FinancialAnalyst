import json
import re
import uuid
import warnings
from pathlib import Path
from typing import Self

import pandas as pd
from llama_index.core.bridge.pydantic import BaseModel
from llama_index.core.evaluation import (
    RetrievalEvalResult,
)
from llama_index.core.evaluation.retrieval.base import RetrievalEvalMode
from llama_index.core.llms import LLM
from llama_index.core.schema import MetadataMode, TextNode
from tqdm import tqdm


class EmbeddingQAFinetuneDataset(BaseModel):
    """
    Embedding QA Finetuning Dataset.

    Args:
        queries (Dict[str, str]): Dict id -> query.
        corpus (Dict[str, str]): Dict id -> string.
        relevant_docs (Dict[str, List[str]]): Dict query id -> list of doc ids.

    """

    queries: dict[str, str]
    corpus: dict[str, str]
    relevant_docs: dict[str, list[str]]
    mode: str = "text"

    @property
    def query_docid_pairs(self) -> list[tuple[str, list[str]]]:
        """Get query, relevant doc ids."""
        return [
            (query, self.relevant_docs[query_id])
            for query_id, query in self.queries.items()
        ]

    def save_json(self, path: str) -> None:
        """
        Save the dataset to a JSON file.

        Args:
            path (str): The file path to save the JSON.

        """
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=4)

    @classmethod
    def from_json(cls, path: str) -> Self:
        """
        Load the dataset from a JSON file.

        Args:
            path (str): The file path to load the JSON from.

        Returns:
            EmbeddingQAFinetuneDataset: The loaded dataset.

        """
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


DEFAULT_QA_GENERATE_PROMPT_TMPL = """\
Context information is below.

---------------------
{context_str}
---------------------

Given the context information and no prior knowledge.
generate only questions based on the below query.

Given the context information and no prior knowledge, generate {num_questions_per_chunk} user-style retrieval questions.

Rules:
- Output only the questions.
- Do not include any introduction, explanation, label, numbering, bullets, or markdown.
- Each question must be answerable from the context alone.
- Each question must be a natural question a user might ask.
- Each question must be on its own line.
"""


def evaluate_dataset(
    self,
    dataset: EmbeddingQAFinetuneDataset,
    show_progress: bool = True,
) -> list[RetrievalEvalResult]:
    """Run synchronous evaluation with dataset."""

    response_jobs = []
    mode = RetrievalEvalMode.from_str(dataset.mode)

    # We can iterate over the dataset synchronously
    iterable = dataset.queries.items()
    if show_progress:
        from tqdm import tqdm

        iterable = tqdm(iterable, desc="Evaluating dataset")

    for query_id, query in iterable:
        expected_ids = dataset.relevant_docs[query_id]

        # Use the synchronous evaluate method directly from the class instance
        eval_result = self.evaluate(query=query, expected_ids=expected_ids, mode=mode)
        response_jobs.append(eval_result)

    return response_jobs


def display_results(name, eval_results: list[RetrievalEvalResult], metrics: list[str]):
    """Display results from evaluate."""

    metric_dicts = []
    for eval_result in eval_results:
        metric_dict = eval_result.metric_vals_dict
        metric_dicts.append(metric_dict)

    full_df = pd.DataFrame(metric_dicts)

    columns = {
        "retrievers": [name],
        **{k: [full_df[k].mean()] for k in metrics},
    }

    metric_df = pd.DataFrame(columns)

    print(metric_df)


def generate_qa_embedding_pairs(
    nodes: list[TextNode],
    llm: LLM,
    qa_generate_prompt_tmpl: str = DEFAULT_QA_GENERATE_PROMPT_TMPL,
    num_questions_per_chunk: int = 1,
    retry_limit: int = 1,
    on_failure: str = "continue",  # options are "fail" or "continue"
    save_every: int = 500,
    output_path: str = "qa_finetune_dataset.json",
    verbose: bool = True,
    steps: int = 1,
) -> EmbeddingQAFinetuneDataset:
    """
    Generate QA pairs from a set of nodes and save periodically.

    Args:
        nodes (List[TextNode]): List of TextNode objects to process.
        llm (LLM): The large language model to use for generating questions.
        qa_generate_prompt_tmpl (str): The template for generating QA prompts.
        num_questions_per_chunk (int): Number of questions to generate per chunk of text.
        retry_limit (int): Number of times to retry on failure.
        on_failure (str): Action to take on repeated failures ('fail' or 'continue').
        save_every (int): Number of nodes to process before saving the dataset.
        output_path (str): The file path to save the JSON output.
        steps (int): Step size for processing nodes (default is 1, meaning every node is processed).
        verbose (bool): If True, print debugging messages.

    Returns:
        EmbeddingQAFinetuneDataset: The generated dataset.

    """
    queries, corpus, relevant_docs = load_existing_data(output_path)

    node_dict = {
        node.node_id: node.get_content(metadata_mode=MetadataMode.NONE)
        for node in nodes
    }

    start_index = len(corpus)

    save_counter = start_index

    for node_id, text in tqdm(
        list(node_dict.items())[start_index::steps], initial=start_index
    ):
        query = qa_generate_prompt_tmpl.format(
            context_str=text, num_questions_per_chunk=num_questions_per_chunk
        )

        retry_count = 0
        success = False
        while retry_count < retry_limit:
            try:
                response = llm.complete(query)
                success = True
                break
            except Exception as e:
                retry_count += 1
                if verbose:
                    print(
                        f"Error querying LLM: {e}. Retrying {retry_count}/{retry_limit}..."
                    )

        if not success:
            if on_failure == "fail":
                raise RuntimeError(f"Failed to query LLM after {retry_limit} retries.")
            elif on_failure == "continue":
                if verbose:
                    print(f"Skipping node {node_id} after {retry_limit} retries.")
                continue

        questions = clean_questions(str(response), num_questions_per_chunk)

        num_questions_generated = len(questions)
        if num_questions_generated < num_questions_per_chunk:
            warnings.warn(
                f"Fewer questions generated ({num_questions_generated}) "
                f"than requested ({num_questions_per_chunk})."
            )

        for question in questions:
            question_id = str(uuid.uuid4())
            queries[question_id] = question
            relevant_docs[question_id] = [node_id]

        corpus[node_id] = text

        save_counter += 1
        if save_counter % save_every == 0:
            dataset = EmbeddingQAFinetuneDataset(
                queries=queries, corpus=corpus, relevant_docs=relevant_docs
            )
            dataset.save_json(output_path)
            if verbose:
                print(f"Saved progress at {save_counter} entries.")

    # Save final dataset
    dataset = EmbeddingQAFinetuneDataset(
        queries=queries, corpus=corpus, relevant_docs=relevant_docs
    )
    dataset.save_json(output_path)
    if verbose:
        print("Final dataset saved.")

    return dataset


def load_existing_data(output_path: str):
    if Path(output_path).exists():
        with open(output_path, "r") as f:
            data = json.load(f)
            return (
                data.get("queries", {}),
                data.get("corpus", {}),
                data.get("relevant_docs", {}),
            )
    return {}, {}, {}


BAD_PATTERNS = [
    r"based solely on the provided context",
    r"based on the provided context",
    r"generate one question",
    r"generate a single question",
    r"here is one question",
    r"^question\s*:?\s*$",
    r"^\*\*question:\*\*$",
]


def clean_questions(raw_text: str, num_questions_per_chunk: int):
    lines = [line.strip() for line in str(raw_text).splitlines() if line.strip()]
    cleaned = []

    for line in lines:
        line = re.sub(r"^\d+[\).\s-]*", "", line).strip()  # Remove 1. or 2) or 3.)
        line = re.sub(r"^-+\s*", "", line).strip()
        line = re.sub(r"^\*\*Question:\*\*\s*", "", line, flags=re.IGNORECASE).strip()
        line = re.sub(r"^Question:\s*", "", line, flags=re.IGNORECASE).strip()

        lower = line.lower()
        if any(re.search(p, lower) for p in BAD_PATTERNS):
            continue
        if not line.endswith("?"):
            continue
        if len(line.split()) < 5:
            continue

        cleaned.append(line)

    return cleaned[:num_questions_per_chunk]
