from llama_index.readers.sec_filings import SECFilingsLoader
from llama_index.core import Settings, VectorStoreIndex, SimpleDirectoryReader, Document, StorageContext, SummaryIndex
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.deepseek import DeepSeek
from llama_index.core.readers.base import BaseReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.indices.document_summary import DocumentSummaryIndex
from liteparse import LiteParse
from typing import Dict
from chromadb.api.models.Collection import Collection
import chromadb



class CustomDocs:

    _v_collection: Collection
    _s_collection: Collection
    _v_collection_size: int
    _s_collection_size: int
    summ_idx: DocumentSummaryIndex
    vec_idx: VectorStoreIndex

    def __init__(self, name: str, path: str, context_description: str, file_extractor: Dict[str, BaseReader] ) -> None:
        self.name = name
        self.extractor = file_extractor
        self.desc = context_description
        self._v_collection, self._v_collection_size, self._s_collection, self._s_collection_size = self._create_collection()
        self.vec_idx, self.summ_idx = self._build_index(path)

    def _create_collection(self):
        db = chromadb.PersistentClient(path="./chroma_db")
        v_chroma_collection = db.get_or_create_collection(f"{self.name}_vector_collection")
        s_chroma_collection = db.get_or_create_collection(f"{self.name}_summ_collection")
        print(f'Creating collection for {self.name} done')

        return v_chroma_collection, v_chroma_collection.count() , v_chroma_collection, s_chroma_collection.count()
    
    
    def _build_index(self,path):
        print(f'Building index for {self.name}')

        v_store = ChromaVectorStore(chroma_collection=self._v_collection)
        v_storage_context = StorageContext.from_defaults(vector_store=v_store)

        s_store = ChromaVectorStore(chroma_collection=self._s_collection)
        s_storage_context = StorageContext.from_defaults(vector_store=s_store)

        if self._v_collection_size == 0 or self._v_collection_size == 0:
            print("Did not find file in collection, parsing it")
            documents = SimpleDirectoryReader(
                input_dir=path,
                file_extractor=self.extractor
                ).load_data()
            
            vec_idx = VectorStoreIndex.from_documents(documents, storage_context=v_storage_context)
            summ_idx = DocumentSummaryIndex.from_documents(documents, storage_context=s_storage_context)
        else:
            print("Found file in collection, skipped parsing")
            vec_idx = VectorStoreIndex.from_vector_store(v_store)

            get_result = self._s_collection.get()
            documents = [Document(text=result) for result in get_result]
            summ_idx = DocumentSummaryIndex.from_documents(documents)

        print(f'Building index for {self.name} done')
        return vec_idx, summ_idx
    
    def get_indexes(self) -> tuple[VectorStoreIndex,DocumentSummaryIndex]:
        return self.vec_idx,self.summ_idx

    def get_tools(self) -> list[QueryEngineTool]:
        v_query_eng = self.vec_idx.as_query_engine(similarity_top_k=3)
        s_query_eng = self.summ_idx.as_query_engine(similarity_top_k=3)

        vector_tool = QueryEngineTool(
            query_engine=v_query_eng,
            metadata=ToolMetadata(
                name=f"vector_tool_{self.name}",
                description=f"Useful to retrieve specific facts and details from {self.desc}."
            )
        )
        summary_tool = QueryEngineTool(
            query_engine=s_query_eng,
            metadata=ToolMetadata(
                name=f"summary_tool_{self.name}",
                description=f"Useful to summarize and get a high-level overview of {self.desc}."
            )
        )

        return [vector_tool, summary_tool]
