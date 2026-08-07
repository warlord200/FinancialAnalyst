from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    SummaryIndex,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.base.response.schema import RESPONSE_TYPE
from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.tools import FunctionTool, QueryEngineTool, ToolMetadata
from llama_index.core.tools.types import AsyncBaseTool
from llama_index.core.vector_stores import (
    FilterCondition,
    MetadataFilters,
)
from llama_index.vector_stores.chroma import ChromaVectorStore

# import logging
# import sys
# logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
# logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


class CustomDocs:
    _v_collection: Collection
    _s_collection: Collection
    _v_collection_size: int
    _s_collection_size: int
    summ_idx: SummaryIndex
    vec_idx: VectorStoreIndex
    _persist_dir: str

    def __init__(
        self,
        name: str,
        path: str,
        context_description: str,
        file_extractor: dict[str, BaseReader],
        chroma_path: str = "./chroma_db",
        storage_base: str = "./storage",
        requires_page_labels: bool = True,
    ) -> None:
        if " " in name:
            raise ValueError("The string must not contain spaces.")
        else:
            self.name = name

        self._extractor = file_extractor
        self.desc = context_description
        self._chroma_path = chroma_path
        self._storage_base = storage_base
        self._requires_page_labels = requires_page_labels
        (
            self._v_collection,
            self._v_collection_size,
            self._s_collection,
            self._s_collection_size,
        ) = self._create_collection()
        self.vec_idx, self.summ_idx = self._build_index(path)

    def _create_collection(self):
        db = chromadb.PersistentClient(path=self._chroma_path)
        v_chroma_collection = db.get_or_create_collection(
            f"{self.name}_vector_collection"
        )
        s_chroma_collection = db.get_or_create_collection(
            f"{self.name}_summ_collection"
        )

        if (
            self._requires_page_labels
            and v_chroma_collection.count() > 0
            and not self._collection_has_page_labels(v_chroma_collection)
        ):
            db.delete_collection(f"{self.name}_vector_collection")
            db.delete_collection(f"{self.name}_summ_collection")
            v_chroma_collection = db.get_or_create_collection(
                f"{self.name}_vector_collection"
            )
            s_chroma_collection = db.get_or_create_collection(
                f"{self.name}_summ_collection"
            )

        print(f"Creating collection for {self.name} done")

        return (
            v_chroma_collection,
            v_chroma_collection.count(),
            s_chroma_collection,
            s_chroma_collection.count(),
        )

    def _collection_has_page_labels(self, collection: Collection) -> bool:
        """Returns True if the collection has page labels, False otherwise

        Usecase: Page labels are used to filter the vector search by page number. If the collection does not have page labels, we need to delete the collection and create a new one with page labels.

        Args:
            collection (Collection): The chroma collection to check for page labels

        Returns:
            bool: True if the collection has page labels, False otherwise
        """
        if collection.count() == 0:
            return False

        sample = collection.get(limit=1, include=["metadatas"])
        metadatas = sample.get("metadatas") or []

        return bool(metadatas and metadatas[0] and "page_label" in metadatas[0])

    def _build_index(self, path: str) -> tuple[VectorStoreIndex, SummaryIndex]:
        """Attempts to build two indexes: a vector index and a summary index.
        If the indexes already exist, it loads them from storage.
        If not, it parses the documents and creates the indexes.

        Args:
            path (str): The path to the document to be indexed

        Returns:
            tuple[VectorStoreIndex, SummaryIndex]: A tuple containing the vector index and the summary index
        """
        print(f"Attempting to build index for {self.name}. Locating file...")
        self._persist_dir = f"{self._storage_base}/{self.name}"
        dir = Path(self._persist_dir)
        dir.mkdir(parents=True, exist_ok=True)

        v_store = ChromaVectorStore(chroma_collection=self._v_collection)
        v_storage_context = StorageContext.from_defaults(vector_store=v_store)

        s_store = ChromaVectorStore(chroma_collection=self._s_collection)

        if self._v_collection_size == 0:
            print("Did not find file in collection, parsing it")
            documents = SimpleDirectoryReader(
                input_files=[path], file_extractor=self._extractor
            ).load_data()
            print("Finished parsing. Building index")

            vec_idx = VectorStoreIndex.from_documents(
                documents, storage_context=v_storage_context
            )

            s_storage_context = StorageContext.from_defaults(vector_store=s_store)
            summ_idx = SummaryIndex.from_documents(
                documents, storage_context=s_storage_context
            )
            summ_idx.storage_context.persist(persist_dir=self._persist_dir)
        else:
            print("Found file in collection, skipped parsing")
            vec_idx = VectorStoreIndex.from_vector_store(
                v_store, storage_context=v_storage_context
            )

            s_storage_context = StorageContext.from_defaults(
                vector_store=s_store, persist_dir=self._persist_dir
            )
            loaded_idx = load_index_from_storage(s_storage_context)
            summ_idx: SummaryIndex = loaded_idx  # type: ignore

        print(
            f"Building index for {self.name} done, Vector size: {len(self._get_nodes_from_chroma(self._v_collection))}, Summary size: {len(summ_idx.docstore.docs)}"
        )
        return vec_idx, summ_idx

    def get_indexes(self) -> tuple[VectorStoreIndex, SummaryIndex]:
        return self.vec_idx, self.summ_idx

    def _vector_query(self, query: str, pg_numbers: list[str]) -> RESPONSE_TYPE:
        """Perform a vector search over an index

        query(str): the string query to be embedded
        pg_numbers (List[str]): Filter by a set of pages. Leave BLANK if we want to perform a vector search over all pages. Otherwise, filter by the set of specified pages

        """

        metadata_dict = [{"key": "page_label", "value": str(p)} for p in pg_numbers]

        # meta_filters = [MetadataFilter.from_dict(filter_dict) for filter_dict in metadata_dict]

        query_eng = self.vec_idx.as_query_engine(
            similarity_top_k=2,
            filters=MetadataFilters.from_dicts(
                metadata_dict, condition=FilterCondition.OR
            ),
        )

        response = query_eng.query(query)

        return response

    def get_tools(self) -> list[AsyncBaseTool]:
        v_query_eng = self.vec_idx.as_query_engine(similarity_top_k=3)
        s_query_eng = self.summ_idx.as_query_engine(response_mode="tree_summarize")

        vector_tool = QueryEngineTool(
            query_engine=v_query_eng,
            metadata=ToolMetadata(
                name=f"vector_tool_{self.name}",
                description=(
                    f"Useful to retrieve specific facts and details from {self.desc}."
                ),
            ),
        )
        summary_tool = QueryEngineTool(
            query_engine=s_query_eng,
            metadata=ToolMetadata(
                name=f"summary_tool_{self.name}",
                description=(
                    f"Useful to summarize and get a high-level overview of {self.desc}."
                ),
            ),
        )

        # This is from L2 tool calling which uses metadataFiltering
        vector_page_tool = FunctionTool.from_defaults(
            name="Vector_search_by_page_tool", fn=self._vector_query
        )

        return [vector_tool, summary_tool, vector_page_tool]

    def _get_nodes_from_chroma(self, collection: Collection) -> list[TextNode]:
        """Returns a list of nodes from chroma

        WHY: Getting a list of nodes index from chroma returns an empty list because the nodes are not stored in the index (docstore is empty), but rather in the chroma collection.
        This function retrieves the nodes from the chroma collection and returns them as a list of BaseNode objects.

        Args:
            collection (Collection): The chroma collection to retrieve nodes from

        Returns:
            List[BaseNode]: List of nodes from the chroma collection
        """
        results = collection.get(include=["metadatas", "documents", "embeddings"])

        if results["documents"] is None:
            print(f"Collection {collection.name} is empty. No nodes to retrieve.")
            return []

        nodes = []

        for i, doc_text in enumerate(results["documents"] or []):
            node = TextNode(
                text=doc_text,
                metadata=results["metadatas"][i] if results["metadatas"] else None,
                # Prevent error: (The truth value of an array with more than one element is ambiguous)
                embedding=results["embeddings"][i]
                if (
                    results["embeddings"] is not None and len(results["embeddings"]) > 0
                )
                else None,
            )
            nodes.append(node)

        return nodes

    def get_vector_nodes(self) -> list[TextNode]:
        """Returns a list of nodes from the vector index

        Usecase: This is useful for evaluating the index and for generating question-context pairs for fine-tuning.

        Returns:
            List[BaseNode]: List of nodes from the vector index
        """
        nodes = self._get_nodes_from_chroma(self._v_collection)

        # To ensure same id's per run, we manually set them
        for idx, node in enumerate(nodes):
            node.id_ = f"node_{idx}"

        self.vec_idx = VectorStoreIndex(nodes=nodes)

        return nodes

    def get_summary_nodes(self) -> list[BaseNode]:
        """Returns a list of nodes from the summary index

        Usecase: This is useful for evaluating the index and for generating question-context pairs for fine-tuning.

        Returns:
            List[BaseNode]: List of nodes from the summary index
        """
        return list(self.vec_idx.docstore.docs.values())
