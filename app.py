import os
import gradio as gr
import helper
import asyncio
import chromadb

from llama_index.readers.sec_filings import SECFilingsLoader
from llama_index.core import Settings, VectorStoreIndex, SimpleDirectoryReader, Document, StorageContext, SummaryIndex
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.deepseek import DeepSeek
from llama_index.core.readers.base import BaseReader
from llama_index.vector_stores.chroma import ChromaVectorStore
from liteparse import LiteParse
from typing import Dict
from utils import CustomDocs


class LiteParseReader(BaseReader):
    def load_data(self, file_path: str, extra_info=None):
        parser = LiteParse(
            output_format="markdown"
        )

        result = parser.parse(file_path)

        return [Document(text=result.text, extra_info=extra_info or {})]

file_extractor: Dict[str, BaseReader] = {".pdf": LiteParseReader()}

print("Initializing LLM and embed model...")
embed_model = HuggingFaceEmbedding(model_name="codefuse-ai/F2LLM-v2-80M")
llm = DeepSeek(model="deepseek-v4-flash", api_key=helper.get_deepseek_api_key())

# Set globally 
Settings.embed_model = embed_model
Settings.llm = llm


# 2. Data Ingestion
print("Downloading SEC fillings...")
# loader = SECFilingsLoader(tickers=["TSLA"], amount=1, filing_type="10-K")
# loader.load_data()

print("Loading documents into memory...")

tesla = CustomDocs("Tesla", "data/2026","Tesla company",file_extractor)

tesla_tools = tesla.get_tools()

# 5. Agent Initialization
agent = ReActAgent(
    tools=tesla_tools, 
    llm=llm, 
    verbose=True
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