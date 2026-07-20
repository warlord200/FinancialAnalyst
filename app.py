import gradio as gr
import helper

# from llama_index.readers.sec_filings import SECFilingsLoader
from llama_index.core import (
    Settings,
    VectorStoreIndex,
    Document,
)

# from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.deepseek import DeepSeek
from llama_index.core.readers.base import BaseReader

# from llama_index.vector_stores.chroma import ChromaVectorStore
from liteparse import LiteParse
from typing import Dict
from CustomDocs import CustomDocs
from FileReader import FileReader
from llama_index.core.objects import ObjectIndex
import torch


class LiteParseReader(BaseReader):
    def load_data(self, file_path: str, extra_info=None):
        parser = LiteParse(output_format="markdown")

        result = parser.parse(file_path)

        base_info = extra_info or {}
        documents = []

        for page in result.pages:
            page_info = {
                **base_info,
                "page_label": str(page.page_num),
                "page_number": page.page_num,
            }
            documents.append(Document(text=page.text, extra_info=page_info))

        return documents


file_extractor: Dict[str, BaseReader] = {".pdf": LiteParseReader()}

print("Initializing LLM and embed model...")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {DEVICE}")
embed_model = HuggingFaceEmbedding(
    model_name="Octen/Octen-Embedding-4B-INT8",
    device=str(DEVICE),
)
llm = DeepSeek(model="deepseek-v4-flash", api_key=helper.get_deepseek_api_key())

# Set globally
Settings.embed_model = embed_model
Settings.llm = llm

# 2. Data Ingestion
print("Downloading SEC fillings...")
# loader = SECFilingsLoader(tickers=["TSLA"], amount=1, filing_type="10-K")
# loader.load_data()

print("Loading documents into memory...")

list_getter = FileReader("./data")
names_dir_list = list_getter.get_fnames_and_dir()

all_tools = []

for company_name, company_file_dir in names_dir_list:
    ctx_desc = company_name + " company"
    company = CustomDocs(company_name, company_file_dir, ctx_desc, file_extractor)
    company_tools = company.get_tools()
    all_tools.extend(company_tools)


obj_index = ObjectIndex.from_objects(
    all_tools,
    index_cls=VectorStoreIndex,
)

obj_retriever = obj_index.as_retriever(similarity_top_k=3)

# 5. Agent Initialization
agent = ReActAgent(
    tool_retriever=obj_retriever,
    llm=llm,
    verbose=True,
)


# 6. UI Setup
async def chat_with_agent(message: str, history):
    result = await agent.run(user_msg=message)
    return str(result)


print("Launching UI...")
demo = gr.ChatInterface(
    fn=chat_with_agent,
    title="Financial Analyst Agent 📈",
    description="Ask questions about Tesla's latest 10-K filing. The agent will retrieve data and answer.",
    examples=["What are the major risk factors?", "Summarize the revenue growth."],
)

if __name__ == "__main__":
    demo.launch()
