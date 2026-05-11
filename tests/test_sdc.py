from __future__ import annotations

from pathlib import Path

import pytest

from eda_parse.loaders import SDCLoader
from eda_parse.parsers import sdc

FIXTURES = Path(__file__).parent / "fixtures" / "sdc"


def test_gcd_sky130_constraint_counts() -> None:
    doc = sdc.parse(FIXTURES / "gcd_sky130hd.sdc")
    assert doc.source_format == "sdc"
    md = doc.metadata
    assert md["clock_count"] == 1
    assert md["input_delay_count"] == 1
    assert md["output_delay_count"] == 1
    assert md["input_transition_count"] == 1
    assert md["false_path_count"] == 0
    assert md["multicycle_path_count"] == 0
    assert md["clock_groups_count"] == 0
    # 4 constraint statements + 3 `set` statements
    assert md["statement_count"] == 7


def test_gcd_sky130_variables_tracked() -> None:
    doc = sdc.parse(FIXTURES / "gcd_sky130hd.sdc")
    variables = doc.metadata["variables"]
    assert variables["period"] == "5"
    assert variables["clk_period_factor"] == ".2"
    # delay is itself a bracket expression — recorded verbatim, not evaluated.
    assert variables["delay"].startswith("[expr")


def test_gcd_sky130_create_clock_period_resolved() -> None:
    """``create_clock -period $period`` should land with period == 5.0
    (resolved from the ``set period 5`` line earlier in the file).
    """
    doc = sdc.parse(FIXTURES / "gcd_sky130hd.sdc")
    clocks = [c for c in doc.chunks if c.kind == "clock"]
    assert len(clocks) == 1
    clock = clocks[0]
    assert clock.metadata["period"] == pytest.approx(5.0)
    assert clock.metadata["command"] == "create_clock"
    # The clock's source is captured as a bracket expression.
    assert clock.metadata["ports"] == "[get_ports clk]"


def test_gcd_sky130_input_delay_metadata() -> None:
    doc = sdc.parse(FIXTURES / "gcd_sky130hd.sdc")
    delays = [c for c in doc.chunks if c.kind == "input_delay"]
    assert len(delays) == 1
    md = delays[0].metadata
    assert md["clock"] == "clk"
    # `delay` here resolves to a bracket expression because the `set delay`
    # value was itself a bracket. We don't try to evaluate [expr ...]; the
    # textual form is preserved.
    assert isinstance(md["delay"], str)
    assert md["delay"].startswith("[expr")


def test_gcd_sky130_input_transition_is_numeric() -> None:
    doc = sdc.parse(FIXTURES / "gcd_sky130hd.sdc")
    [tr] = [c for c in doc.chunks if c.kind == "input_transition"]
    assert tr.metadata["transition"] == pytest.approx(0.1)


def test_set_false_path_extracts_from_to() -> None:
    src = "set_false_path -from [get_ports a] -to [get_ports b]\n"
    doc = sdc.parse_string(src)
    [fp] = [c for c in doc.chunks if c.kind == "false_path"]
    assert fp.metadata["from"] == "[get_ports a]"
    assert fp.metadata["to"] == "[get_ports b]"


def test_set_multicycle_path_cycle_count_is_int() -> None:
    src = "set_multicycle_path 2 -from [get_pins r1/Q] -to [get_pins r2/D] -setup\n"
    doc = sdc.parse_string(src)
    [mc] = [c for c in doc.chunks if c.kind == "multicycle_path"]
    assert mc.metadata["cycles"] == 2
    assert mc.metadata["setup"] is True


def test_set_clock_groups_groups_are_list() -> None:
    src = (
        "set_clock_groups -asynchronous "
        "-group {clk_a clk_b} "
        "-group {clk_c}\n"
    )
    doc = sdc.parse_string(src)
    [g] = [c for c in doc.chunks if c.kind == "clock_groups"]
    assert g.metadata["asynchronous"] is True
    assert g.metadata["groups"] == ["clk_a clk_b", "clk_c"]


def test_sdc_loader_returns_langchain_documents() -> None:
    path = FIXTURES / "gcd_sky130hd.sdc"
    docs = SDCLoader(path).load()
    assert len(docs) == 4  # create_clock + input_delay + output_delay + input_transition
    md0 = docs[0].metadata
    assert md0["source_format"] == "sdc"
    assert md0["source"] == str(path)
    assert md0["chunk_kind"] == "clock"
    # doc-level fields are namespaced under doc_*
    assert "doc_clock_count" in md0
