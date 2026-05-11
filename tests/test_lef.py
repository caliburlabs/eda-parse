from __future__ import annotations

from pathlib import Path

import pytest

from eda_parse.loaders import LEFLoader
from eda_parse.parsers import lef

FIXTURES = Path(__file__).parent / "fixtures" / "lef"


@pytest.mark.parametrize(
    ("filename", "kind", "layer_count", "macro_count", "site_count", "via_count"),
    [
        ("sky130_fd_sc_hd.tlef", "tech", 13, 0, 2, 25),
        ("sky130_fd_sc_hd_merged.lef", "cell", 0, 441, 0, 0),
    ],
)
def test_lef_parser_counts_real_fixtures(
    filename: str,
    kind: str,
    layer_count: int,
    macro_count: int,
    site_count: int,
    via_count: int,
) -> None:
    doc = lef.parse(FIXTURES / filename)

    assert doc.source_format == "lef"
    assert doc.metadata["lef_kind"] == kind
    assert doc.metadata["layer_count"] == layer_count
    assert doc.metadata["macro_count"] == macro_count
    assert doc.metadata["site_count"] == site_count
    assert doc.metadata["via_count"] == via_count
    assert len(doc.chunks) == macro_count


def test_lef_macro_chunk_metadata() -> None:
    doc = lef.parse(FIXTURES / "sky130_fd_sc_hd_merged.lef")
    first = doc.chunks[0]

    assert first.kind == "macro"
    assert first.metadata["macro_name"] == "sky130_ef_sc_hd__decap_12"
    assert first.metadata["class"] == "BLOCK"
    assert first.metadata["pin_count"] == 4
    assert first.metadata["has_obs"] is False
    assert "macro sky130_ef_sc_hd__decap_12" in first.content


def test_lef_langchain_loader_emits_macro_documents() -> None:
    path = FIXTURES / "sky130_fd_sc_hd_merged.lef"
    docs = LEFLoader(path).load()

    assert len(docs) == 441
    assert docs[0].metadata["source_format"] == "lef"
    assert docs[0].metadata["source"] == str(path)
    assert docs[0].metadata["chunk_kind"] == "macro"
    assert docs[0].metadata["macro_name"] == "sky130_ef_sc_hd__decap_12"
