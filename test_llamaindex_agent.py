from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, ServiceContext
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.evaluation import (
    RetrieverEvaluator,
    BaseRetrievalEvaluator,
)
from pathlib import Path
from FileReader import FileReader
from CustomDocs import CustomDocs
from app import llm, obj_retriever, file_extractor
import asyncio
from typing import List, Dict, Tuple
from eval_utils import (
    evaluate_dataset,
    display_results,
    EmbeddingQAFinetuneDataset,
    generate_qa_embedding_pairs,
)

BaseRetrievalEvaluator.evaluate_dataset = evaluate_dataset  # type: ignore

list_getter = FileReader("./data")
names_dir_list = list_getter.get_fnames_and_dir()
names_store_list = list_getter.get_storage_location(
    new_file="train_dataset.json", storage_dir="./storage/evals"
)

all_tools = []
datasets = []

METRICS = ["mrr", "hit_rate"]

for i, (company_name, company_file_dir) in enumerate(names_dir_list):
    ctx_desc = company_name + " company"
    company = CustomDocs(company_name, company_file_dir, ctx_desc, file_extractor)
    nodes = company.get_vector_nodes()
    f_path = names_store_list[i][1]  # Get the storage path for the dataset

    retriever = company.vec_idx.as_retriever(similarity_top_k=2)

    print(f"Generating QA dataset for {company_name}...")
    if Path(f_path).is_file():
        print(f"Dataset already exists for {company_name}. Skipping generation.")
        qa_dataset = EmbeddingQAFinetuneDataset.from_json(f_path)

    else:
        qa_dataset = generate_qa_embedding_pairs(
            nodes, llm=llm, num_questions_per_chunk=1, output_path=f_path, steps=1
        )

    retriever_evaluator = RetrieverEvaluator.from_metric_names(
        METRICS, retriever=retriever
    )

    print(f"Evaluating dataset for {company_name}...")
    eval_results = retriever_evaluator.evaluate_dataset(  # type: ignore
        qa_dataset, show_progress=True
    )

    display_results(company_name, eval_results, METRICS)
