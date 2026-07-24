from pathlib import Path

from llama_index.core.evaluation import (
    BaseRetrievalEvaluator,
    RetrieverEvaluator,
)

from financial_analyst.app import file_extractor, llm  # , DEVICE
from financial_analyst.evaluation.eval_utils import (
    EmbeddingQAFinetuneDataset,
    display_results,
    evaluate_dataset,
    generate_qa_embedding_pairs,
)
from financial_analyst.indexing.CustomDocs import CustomDocs
from financial_analyst.ingestion.file_reader import FileReader

# from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker

BaseRetrievalEvaluator.evaluate_dataset = evaluate_dataset  # type: ignore

# Reranking is not implemented because all open sourced models are not fine tuned for financial data (23/7)
# Any attempts at reranking with open source models will result in poor performance. The best approach is to use a fine tuned open model for financial data
# postprocessor = FlagEmbeddingReranker(
#     model="BAAI/bge-reranker-v2-m3",
#     top_n=2,
#     use_fp16=True,
# )

list_getter = FileReader("./data")
names_dir_list = list_getter.get_fnames_and_dir()
names_store_list = list_getter.get_storage_location(
    new_file="train_dataset.json", storage_dir="./storage/evals"
)

all_tools = []
datasets = []

# MRR is a measure of how well the model ranks the relevant documents. A higher MRR indicates that the model is better at ranking relevant documents higher in the list of retrieved documents.
# Hit Rate is a measure of how many relevant documents are retrieved by the model. A higher hit rate indicates that the model is better at retrieving relevant documents, regardless of their rank in the list of retrieved documents.
METRICS = ["mrr", "hit_rate", "ndcg"]

for i, (company_name, company_file_dir) in enumerate(names_dir_list):
    ctx_desc = company_name + " company"
    company = CustomDocs(company_name, company_file_dir, ctx_desc, file_extractor)
    nodes = company.get_vector_nodes()
    f_path = names_store_list[i][1]  # Get the storage path for the dataset

    # Larger k value = higher hit rate but lower MRR. Smaller k value = lower hit rate but higher MRR
    retriever = company.vec_idx.as_retriever(similarity_top_k=4)

    print(f"Generating QA dataset for {company_name}...")
    if Path(f_path).is_file():
        print(f"Dataset already exists for {company_name}. Skipping generation.")
        qa_dataset = EmbeddingQAFinetuneDataset.from_json(f_path)

    else:
        qa_dataset = generate_qa_embedding_pairs(
            nodes, llm=llm, num_questions_per_chunk=1, output_path=f_path, steps=1
        )

    retriever_evaluator = RetrieverEvaluator.from_metric_names(
        METRICS,
        retriever=retriever,  # node_postprocessors=[postprocessor]
    )

    print(f"Evaluating dataset for {company_name}...")
    eval_results = retriever_evaluator.evaluate_dataset(  # type: ignore
        qa_dataset, show_progress=True
    )

    display_results(company_name, eval_results, METRICS)
