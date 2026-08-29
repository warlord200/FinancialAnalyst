import re
from pathlib import Path

from lxml import html
from llama_index.core import Document
from llama_index.core.readers.base import BaseReader

ITEM_RE = re.compile(r"(?i)^\s*item\s+(\d{1,3}(?:[a-z]|\([a-z]\))?)\b")

TOC_TINY = 1000

BLOCK_TAGS = {
    "br",
    "div",
    "p",
    "li",
    "tr",
    "td",
    "table",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "section",
    "ul",
    "ol",
}


def _extract_ticker_year(file_path: str) -> tuple[str | None, int | None]:
    p = Path(file_path)
    ticker = p.stem.upper() or None
    parent = p.parent.name
    year = int(parent) if parent.isdigit() else None
    return ticker, year


def _inject_block_newlines(tree):
    for el in tree.iter():
        if el.tag in BLOCK_TAGS:
            el.tail = (el.tail or "") + "\n"


class SECHtmlReader(BaseReader):
    def load_data(self, file_path: str, extra_info: dict | None = None):
        extra_info = extra_info or {}
        tree = html.fromstring(Path(file_path).read_bytes())
        for tag in tree.xpath("//script | //style"):
            tag.getparent().remove(tag)
        _inject_block_newlines(tree)
        text = tree.text_content()

        ticker, path_year = _extract_ticker_year(file_path)
        ticker = (extra_info.get("ticker") or ticker or "").upper()
        fiscal_year = extra_info.get("fiscal_year") or path_year

        lines = text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_item: str | None = None
        current_lines: list[str] = []

        for line in lines:
            m = ITEM_RE.match(line)
            if m:
                if current_item is not None and "".join(current_lines).strip():
                    sections.append((current_item, current_lines))
                current_item = f"ITEM {m.group(1).upper()}"
                current_lines = [line]
            elif current_item is not None:
                current_lines.append(line)
        if current_item is not None and "".join(current_lines).strip():
            sections.append((current_item, current_lines))

        documents = []
        label_total = {}
        for item, _ in sections:
            label_total[item] = label_total.get(item, 0) + 1
        seen = {}
        for item, item_lines in sections:
            seen[item] = seen.get(item, 0) + 1
            body = "\n".join(line for line in item_lines if line.strip()).strip()
            if not body:
                continue
            has_later_duplicate = label_total[item] - seen[item] > 0
            if has_later_duplicate and len(body) < TOC_TINY:
                continue
            documents.append(
                Document(
                    text=body,
                    extra_info={
                        "ticker": ticker,
                        "fiscal_year": fiscal_year,
                        "item": item,
                    },
                )
            )
        return documents
