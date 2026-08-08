import torch
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.deepseek import DeepSeek

from financial_analyst import config
from financial_analyst.analysis.analyzer import Analyzer
from financial_analyst.ingestion.sec_downloader import SECDownloader
from financial_analyst.reader.sec_html_reader import SECHtmlReader
from financial_analyst.storage.registry import CacheRegistry

_analyzer: Analyzer | None = None


def get_analyzer() -> Analyzer:
    global _analyzer
    if _analyzer is not None:
        return _analyzer

    device = str(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    embed_model = HuggingFaceEmbedding(
        model_name="Octen/Octen-Embedding-4B-INT8",
        device=device,
    )
    llm = DeepSeek(model="deepseek-v4-flash", api_key=config.get_deepseek_api_key())

    Settings.embed_model = embed_model
    Settings.llm = llm

    downloader = SECDownloader(data_dir="./data")
    registry = CacheRegistry("./storage/registry.json")
    file_extractor = {".htm": SECHtmlReader()}

    _analyzer = Analyzer(
        downloader,
        registry,
        llm,
        chroma_path="./chroma_db",
        storage_base="./storage",
        file_extractor=file_extractor,
    )
    return _analyzer
