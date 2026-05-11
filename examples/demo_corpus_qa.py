#!/usr/bin/env python3
"""Concrete-question demo over a parsed EDA corpus.

This is *not* "chat with your files". Most useful questions over a chip
design can be answered with structured filters on the metadata that
``eda-parse`` extracts — no embedding model, no LLM. The point of this
script is to show that.

Each question below runs against the same three real fixtures the test
suite uses (SKY130 ``sky130_fd_sc_hd`` library + merged LEF + a
``gcd_sky130hd`` SDC). The library is doing the work; this script just
projects answers out of the parsed objects.

Run it with:

    python examples/demo_corpus_qa.py

Optional: ``--with-rag`` adds a follow-up demonstrating that the same
chunks plug into a LangChain vectorstore for the open-ended questions
that *do* benefit from retrieval. It is gated behind that flag because
the rest of the script runs in well under a second with zero ML deps.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from eda_parse.parsers import lef, liberty, sdc

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"

LIBERTY_PATH = FIXTURES / "liberty" / "sky130hd_tt.lib.gz"
LEF_PATH = FIXTURES / "lef" / "sky130_fd_sc_hd_merged.lef"
SDC_PATH = FIXTURES / "sdc" / "gcd_sky130hd.sdc"


# ----------------------------------------------------------------------
# Pretty-printing helpers (no external dep)
# ----------------------------------------------------------------------


def heading(text: str) -> None:
    bar = "─" * len(text)
    print(f"\n{text}\n{bar}")


def bullet(text: str) -> None:
    print(f"  • {text}")


# ----------------------------------------------------------------------
# Question 1: What clocks exist in this design?
# ----------------------------------------------------------------------


def answer_clocks(sdc_doc: Any) -> None:
    heading("Q1. What clocks exist in this design?")
    clocks = [c for c in sdc_doc.chunks if c.kind == "clock"]
    if not clocks:
        bullet("No clocks defined.")
        return
    for c in clocks:
        period = c.metadata.get("period")
        period_str = f"{period} ns" if isinstance(period, float) else str(period)
        name = c.metadata.get("name") or "(unnamed — defaults to source port)"
        ports = c.metadata.get("ports", "<unspecified>")
        bullet(f"clock: {name}")
        print(f"      period: {period_str}")
        print(f"      source: {ports}")

    gens = [c for c in sdc_doc.chunks if c.kind == "generated_clock"]
    if gens:
        bullet(f"+ {len(gens)} generated clock(s)")


# ----------------------------------------------------------------------
# Question 2: What standard cells are characterized in the Liberty?
# ----------------------------------------------------------------------


def answer_cells(lib_doc: Any) -> None:
    heading("Q2. What standard cells are characterized in the Liberty library?")
    bullet(f"library: {lib_doc.metadata.get('library')}")
    bullet(f"cell count: {lib_doc.metadata.get('cell_count')}")
    bullet(f"total pin count: {lib_doc.metadata.get('total_pin_count')}")

    # Group cells by their stem (everything before the size suffix, e.g.
    # `sky130_fd_sc_hd__and2_1` → `sky130_fd_sc_hd__and2`).
    families: Counter[str] = Counter()
    for chunk in lib_doc.chunks:
        name = chunk.metadata.get("cell_name", "")
        stem = name.rsplit("_", 1)[0] if "_" in name else name
        families[stem] += 1

    print(f"      {len(families)} distinct cell families. Top 8 by drive-strength count:")
    for stem, n in families.most_common(8):
        short = stem.replace("sky130_fd_sc_hd__", "")
        print(f"        - {short}: {n} drive strengths")


# ----------------------------------------------------------------------
# Question 3: What physical macros exist in the LEF?
# ----------------------------------------------------------------------


def answer_macros(lef_doc: Any) -> None:
    heading("Q3. What physical macros exist in the LEF (sizes, classes)?")
    bullet(f"LEF kind: {lef_doc.metadata.get('lef_kind')}")
    bullet(f"macro count: {lef_doc.metadata.get('macro_count')}")
    bullet(f"layer count: {lef_doc.metadata.get('layer_count')}")
    bullet(f"site count: {lef_doc.metadata.get('site_count')}")

    by_class: Counter[str] = Counter()
    sizes: list[tuple[str, float, float]] = []
    for chunk in lef_doc.chunks:
        md = chunk.metadata
        cls = str(md.get("class") or "?")
        by_class[cls] += 1
        w = md.get("width")
        h = md.get("height")
        if isinstance(w, float) and isinstance(h, float):
            sizes.append((str(md.get("macro_name")), w, h))

    print(f"      macro classes: {dict(by_class)}")
    if sizes:
        sizes.sort(key=lambda t: t[1] * t[2])
        smallest = sizes[0]
        largest = sizes[-1]
        print(f"      smallest macro: {smallest[0]} ({smallest[1]} x {smallest[2]})")
        print(f"      largest macro:  {largest[0]} ({largest[1]} x {largest[2]})")


# ----------------------------------------------------------------------
# Question 4: What PVT corner is this Liberty characterized for?
# ----------------------------------------------------------------------


def answer_pvt(lib_doc: Any) -> None:
    heading("Q4. What PVT corner is this Liberty characterized for?")
    md = lib_doc.metadata
    bullet(f"technology: {md.get('technology')}")
    bullet(f"delay_model: {md.get('delay_model')}")
    bullet(f"nominal process: {md.get('nom_process')}")
    bullet(f"nominal voltage: {md.get('nom_voltage')} V")
    bullet(f"nominal temperature: {md.get('nom_temperature')} °C")
    bullet(f"units: time={md.get('time_unit')}, voltage={md.get('voltage_unit')}, current={md.get('current_unit')}")
    op = md.get("operating_conditions") or []
    if op:
        bullet("operating conditions group(s):")
        for oc in op:
            print(
                f"      - {oc.get('name')}: "
                f"process={oc.get('process')}, "
                f"voltage={oc.get('voltage')} V, "
                f"temperature={oc.get('temperature')} °C"
            )


# ----------------------------------------------------------------------
# Question 5: Cross-doc — do the SDC-named ports look like real things?
# ----------------------------------------------------------------------


def answer_cross_check(sdc_doc: Any, lef_doc: Any, lib_doc: Any) -> None:
    heading("Q5. Cross-check: do constraint targets in the SDC reference real cells/macros?")
    # Pull every distinct token that looks like a cell/macro reference out of
    # SDC chunk metadata.
    referenced: set[str] = set()
    for chunk in sdc_doc.chunks:
        for v in chunk.metadata.values():
            if isinstance(v, str):
                for tok in v.replace("[", " ").replace("]", " ").split():
                    if tok and tok.replace("_", "").isalnum() and not tok.startswith("$"):
                        referenced.add(tok)

    cell_names = {c.metadata.get("cell_name") for c in lib_doc.chunks}
    macro_names = {c.metadata.get("macro_name") for c in lef_doc.chunks}

    hits_lib = sorted(t for t in referenced if t in cell_names)
    hits_lef = sorted(t for t in referenced if t in macro_names)

    bullet(f"distinct tokens pulled from SDC: {len(referenced)}")
    bullet(f"matches against Liberty cell names: {len(hits_lib)}")
    bullet(f"matches against LEF macro names:    {len(hits_lef)}")
    if hits_lib:
        print(f"      Liberty matches: {hits_lib[:5]}")
    if hits_lef:
        print(f"      LEF matches:     {hits_lef[:5]}")
    if not hits_lib and not hits_lef:
        print("      (No matches expected — gcd SDC names design-level ports, not library cells.)")


# ----------------------------------------------------------------------
# Optional RAG path
# ----------------------------------------------------------------------


def maybe_rag_demo(
    lib_doc: Any, lef_doc: Any, sdc_doc: Any, enabled: bool
) -> None:
    if not enabled:
        return
    heading("Q6 (--with-rag). Open-ended retrieval over the parsed corpus")
    try:
        from langchain_community.vectorstores import FAISS  # type: ignore[import-not-found]
        from langchain_huggingface import (  # type: ignore[import-not-found]
            HuggingFaceEmbeddings,
        )
    except ImportError:
        bullet(
            "RAG path needs `langchain-community` and `langchain-huggingface` "
            "(plus a sentence-transformers model). Install with: "
            "pip install langchain-community langchain-huggingface sentence-transformers faiss-cpu"
        )
        return

    all_docs = (
        lib_doc.to_langchain_documents()
        + lef_doc.to_langchain_documents()
        + sdc_doc.to_langchain_documents()
    )
    bullet(f"indexing {len(all_docs)} chunks across Liberty + LEF + SDC")
    emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vs = FAISS.from_documents(all_docs, emb)
    for query in [
        "What buffer cells are available with multiple drive strengths?",
        "Which macros are filler cells?",
        "What is the input transition constraint?",
    ]:
        hits = vs.similarity_search(query, k=3)
        bullet(f"query: {query}")
        for h in hits:
            kind = h.metadata.get("chunk_kind", "?")
            cid = h.metadata.get("chunk_id", "?")
            first_line = h.page_content.split("\n", 1)[0]
            print(f"      [{kind}] {cid} :: {first_line}")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--with-rag", action="store_true", help="also run the optional RAG demo")
    args = ap.parse_args()

    print("eda-parse — corpus QA demo")
    print(f"  Liberty: {LIBERTY_PATH.relative_to(REPO_ROOT)}")
    print(f"  LEF:     {LEF_PATH.relative_to(REPO_ROOT)}")
    print(f"  SDC:     {SDC_PATH.relative_to(REPO_ROOT)}")

    lib_doc = liberty.parse(LIBERTY_PATH)
    lef_doc = lef.parse(LEF_PATH)
    sdc_doc = sdc.parse(SDC_PATH)

    answer_clocks(sdc_doc)
    answer_cells(lib_doc)
    answer_macros(lef_doc)
    answer_pvt(lib_doc)
    answer_cross_check(sdc_doc, lef_doc, lib_doc)
    maybe_rag_demo(lib_doc, lef_doc, sdc_doc, args.with_rag)


if __name__ == "__main__":
    main()
