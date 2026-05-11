from __future__ import annotations

from eda_parse.types import Chunk, ParsedDocument


def test_parsed_document_roundtrips_via_pydantic() -> None:
    doc = ParsedDocument(
        content="hello",
        metadata={"library": "lib0", "cell_count": 1},
        source_format="liberty",
        chunks=[
            Chunk(
                id="lib0::AND2_X1",
                kind="cell",
                content="cell AND2_X1",
                metadata={"area": 1.0, "pin_count": 3},
            )
        ],
    )
    dumped = doc.model_dump()
    assert dumped["metadata"]["library"] == "lib0"
    assert dumped["chunks"][0]["id"] == "lib0::AND2_X1"
    assert dumped["chunks"][0]["metadata"]["area"] == 1.0


def test_to_langchain_documents_namespaces_doc_metadata() -> None:
    doc = ParsedDocument(
        content="hello",
        metadata={"library": "lib0", "technology": "cmos"},
        source_format="liberty",
        chunks=[
            Chunk(
                id="lib0::c0",
                kind="cell",
                content="cell c0",
                metadata={"area": 0.5, "library": "should-not-clobber"},
            )
        ],
    )
    lc = doc.to_langchain_documents()
    assert len(lc) == 1
    md = lc[0].metadata
    # Document-level keys are prefixed with doc_ to avoid collisions with
    # per-chunk keys of the same name.
    assert md["doc_library"] == "lib0"
    assert md["doc_technology"] == "cmos"
    # Per-chunk metadata keeps its own keys
    assert md["library"] == "should-not-clobber"
    assert md["area"] == 0.5
    # Routing keys
    assert md["source_format"] == "liberty"
    assert md["chunk_id"] == "lib0::c0"
    assert md["chunk_kind"] == "cell"
    assert lc[0].page_content == "cell c0"


def test_to_langchain_documents_with_no_chunks() -> None:
    doc = ParsedDocument(
        content="empty",
        metadata={},
        source_format="lef",
        chunks=[],
    )
    assert doc.to_langchain_documents() == []
