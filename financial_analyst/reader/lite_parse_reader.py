from liteparse import LiteParse
from llama_index.core import Document
from llama_index.core.readers.base import BaseReader


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
