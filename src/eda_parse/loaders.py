"""LangChain document loaders for eda-parse formats."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from eda_parse.parsers import lef, liberty, sdc


class LibertyLoader(BaseLoader):
    """Load a Liberty file as one LangChain document per cell chunk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def lazy_load(self) -> Iterator[Document]:
        parsed = liberty.parse(self.path)
        for doc in parsed.to_langchain_documents():
            doc.metadata["source"] = str(self.path)
            yield doc


class LEFLoader(BaseLoader):
    """Load a LEF file as one LangChain document per MACRO chunk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def lazy_load(self) -> Iterator[Document]:
        parsed = lef.parse(self.path)
        for doc in parsed.to_langchain_documents():
            doc.metadata["source"] = str(self.path)
            yield doc


class SDCLoader(BaseLoader):
    """Load an SDC file as one LangChain document per constraint chunk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def lazy_load(self) -> Iterator[Document]:
        parsed = sdc.parse(self.path)
        for doc in parsed.to_langchain_documents():
            doc.metadata["source"] = str(self.path)
            yield doc

