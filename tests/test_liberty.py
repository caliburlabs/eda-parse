from __future__ import annotations

from pathlib import Path

import pytest

from eda_parse.loaders import LibertyLoader
from eda_parse.parsers import liberty

FIXTURES = Path(__file__).parent / "fixtures" / "liberty"


@pytest.mark.parametrize(
    ("filename", "library", "cell_count", "pin_count"),
    [
        ("asap7_small_ff.lib.gz", "asap7_small_ff", 3, 8),
        ("asap7_small_ss.lib.gz", "asap7_small_ss", 3, 8),
        ("sky130hd_tt.lib.gz", "sky130_fd_sc_hd__tt_025C_1v80", 428, 1771),
    ],
)
def test_liberty_parser_counts_real_fixtures(
    filename: str,
    library: str,
    cell_count: int,
    pin_count: int,
) -> None:
    doc = liberty.parse(FIXTURES / filename)

    assert doc.source_format == "liberty"
    assert doc.metadata["library"] == library
    assert doc.metadata["cell_count"] == cell_count
    assert doc.metadata["total_pin_count"] == pin_count
    assert len(doc.chunks) == cell_count


def test_liberty_cell_chunk_metadata() -> None:
    doc = liberty.parse(FIXTURES / "sky130hd_tt.lib.gz")
    first = doc.chunks[0]

    assert first.kind == "cell"
    assert first.metadata["cell_name"] == "sky130_fd_sc_hd__a2111o_1"
    assert first.metadata["pin_directions"] == {
        "A1": "input",
        "A2": "input",
        "B1": "input",
        "C1": "input",
        "D1": "input",
        "X": "output",
    }
    assert first.metadata["functions"] == {
        "X": "(A1&A2) | (B1) | (C1) | (D1)",
    }
    assert "cell sky130_fd_sc_hd__a2111o_1" in first.content


def test_liberty_langchain_loader_emits_cell_documents() -> None:
    path = FIXTURES / "asap7_small_ff.lib.gz"
    docs = LibertyLoader(path).load()

    assert len(docs) == 3
    assert docs[0].metadata["source_format"] == "liberty"
    assert docs[0].metadata["source"] == str(path)
    assert docs[0].metadata["chunk_kind"] == "cell"
    assert "BUFx2_ASAP7_75t_R" in docs[0].page_content
