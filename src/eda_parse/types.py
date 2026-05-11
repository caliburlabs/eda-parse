"""Unified document and chunk types every parser conforms to.

Every parser in eda-parse returns a ``ParsedDocument``. The document carries
both a human-readable rendering (``content``) and a list of semantic
``Chunk`` objects suitable for embedding and retrieval. The structured
``metadata`` dict holds format-specific extracted fields (cell counts, PVT
corners, layer names, etc.) and is preserved end-to-end into LangChain
``Document.metadata`` so RAG pipelines can filter on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langchain_core.documents import Document as LCDocument

SourceFormat = Literal[
    "liberty",
    "lef",
    "def",
    "vcd",
    "sdc",
    "spef",
]


class Chunk(BaseModel):
    """A semantic chunk of an EDA artifact, ready for embedding.

    Chunks are the retrieval unit. For Liberty that means one chunk per
    library cell; for LEF, one chunk per MACRO; for DEF, one chunk per
    component or net group; etc. The ``kind`` field records which logical
    unit the chunk represents so downstream consumers can filter cheaply.
    """

    id: str = Field(..., description="Stable, content-derived chunk id.")
    kind: str = Field(..., description="Semantic unit: 'cell', 'macro', 'net', 'signal', ...")
    content: str = Field(..., description="Human-readable rendering for embedding.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """Unified return type for all eda-parse parsers."""

    model_config = {"arbitrary_types_allowed": True}

    content: str = Field(..., description="Top-level human-readable rendering.")
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_format: SourceFormat
    chunks: list[Chunk] = Field(default_factory=list)
    raw: Any = Field(default=None, description="Underlying AST or struct if needed.")

    def to_langchain_documents(self) -> list[LCDocument]:
        """Convert chunks into LangChain ``Document`` objects.

        Each ``Chunk`` becomes one ``Document`` whose ``page_content`` is the
        chunk content and whose ``metadata`` merges the document-level
        metadata, the chunk-level metadata, and routing keys
        (``source_format``, chunk ``id`` and ``kind``). Document-level keys
        are namespaced under ``doc_*`` to avoid collision with chunk keys.
        """
        try:
            from langchain_core.documents import Document as LCDocument
        except ImportError as exc:  # pragma: no cover - import-time path
            raise ImportError(
                "to_langchain_documents() requires langchain-core. "
                "Install with: pip install 'eda-parse[langchain]'"
            ) from exc

        doc_meta = {f"doc_{k}": v for k, v in self.metadata.items()}
        out: list[LCDocument] = []
        for chunk in self.chunks:
            md: dict[str, Any] = {
                "source_format": self.source_format,
                "chunk_id": chunk.id,
                "chunk_kind": chunk.kind,
                **doc_meta,
                **chunk.metadata,
            }
            out.append(LCDocument(page_content=chunk.content, metadata=md))
        return out
