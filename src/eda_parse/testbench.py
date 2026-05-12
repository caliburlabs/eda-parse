"""Open-corpus workflow testbench for eda-parse.

This module is intentionally stricter than the example script. The example
shows what a user can ask; the testbench defines what this repo promises:
given real public EDA artifacts, the parsers extract stable facts, produce
retrieval-ready chunks, and finish within an ingest-path latency budget.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from eda_parse.parsers import lef, liberty, sdc
from eda_parse.types import ParsedDocument


@dataclass(frozen=True)
class CheckResult:
    """One acceptance criterion in the workflow testbench."""

    name: str
    passed: bool
    observed: Any
    expected: Any
    detail: str = ""


@dataclass(frozen=True)
class WorkflowQuestion:
    """A concrete question the parsed corpus must answer."""

    id: str
    question: str
    answer: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class TestbenchReport:
    """Complete workflow testbench result."""

    corpus: dict[str, str]
    parse_seconds: float
    artifact_counts: dict[str, Any]
    checks: list[CheckResult]
    questions: list[WorkflowQuestion]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"passed": self.passed}


def _fixture_paths(repo_root: Path) -> dict[str, Path]:
    fixtures = repo_root / "tests" / "fixtures"
    return {
        "liberty": fixtures / "liberty" / "sky130hd_tt.lib.gz",
        "lef": fixtures / "lef" / "sky130_fd_sc_hd_merged.lef",
        "sdc": fixtures / "sdc" / "gcd_sky130hd.sdc",
    }


def _cell_family_counts(lib_doc: ParsedDocument) -> Counter[str]:
    families: Counter[str] = Counter()
    for chunk in lib_doc.chunks:
        name = str(chunk.metadata.get("cell_name", ""))
        stem = name.rsplit("_", 1)[0] if "_" in name else name
        families[stem.replace("sky130_fd_sc_hd__", "")] += 1
    return families


def _macro_class_counts(lef_doc: ParsedDocument) -> Counter[str]:
    counts: Counter[str] = Counter()
    for chunk in lef_doc.chunks:
        cls = str(chunk.metadata.get("class") or "?")
        counts[cls] += 1
    return counts


def _macro_size_range(lef_doc: ParsedDocument) -> dict[str, Any]:
    sizes: list[tuple[str, float, float]] = []
    for chunk in lef_doc.chunks:
        width = chunk.metadata.get("width")
        height = chunk.metadata.get("height")
        if isinstance(width, float) and isinstance(height, float):
            sizes.append((str(chunk.metadata.get("macro_name")), width, height))
    sizes.sort(key=lambda item: item[1] * item[2])
    smallest = sizes[0]
    largest = sizes[-1]
    return {
        "smallest": {
            "name": smallest[0],
            "width": smallest[1],
            "height": smallest[2],
        },
        "largest": {
            "name": largest[0],
            "width": largest[1],
            "height": largest[2],
        },
    }


def _sdc_reference_matches(
    sdc_doc: ParsedDocument,
    lef_doc: ParsedDocument,
    lib_doc: ParsedDocument,
) -> dict[str, Any]:
    referenced: set[str] = set()
    for chunk in sdc_doc.chunks:
        for value in chunk.metadata.values():
            if isinstance(value, str):
                for token in value.replace("[", " ").replace("]", " ").split():
                    if token and token.replace("_", "").isalnum() and not token.startswith("$"):
                        referenced.add(token)

    cell_names = {chunk.metadata.get("cell_name") for chunk in lib_doc.chunks}
    macro_names = {chunk.metadata.get("macro_name") for chunk in lef_doc.chunks}
    liberty_hits = sorted(token for token in referenced if token in cell_names)
    lef_hits = sorted(token for token in referenced if token in macro_names)
    return {
        "referenced_token_count": len(referenced),
        "liberty_cell_matches": liberty_hits,
        "lef_macro_matches": lef_hits,
    }


def _chunk_kind_counts(*docs: ParsedDocument) -> Counter[str]:
    counts: Counter[str] = Counter()
    for doc in docs:
        for chunk in doc.chunks:
            counts[f"{doc.source_format}:{chunk.kind}"] += 1
    return counts


def _check(name: str, observed: Any, expected: Any, detail: str = "") -> CheckResult:
    return CheckResult(
        name=name,
        passed=observed == expected,
        observed=observed,
        expected=expected,
        detail=detail,
    )


def _check_at_most(name: str, observed: float, expected: float, detail: str = "") -> CheckResult:
    return CheckResult(
        name=name,
        passed=observed <= expected,
        observed=round(observed, 4),
        expected=f"<= {expected}",
        detail=detail,
    )


def _build_questions(
    lib_doc: ParsedDocument,
    lef_doc: ParsedDocument,
    sdc_doc: ParsedDocument,
) -> list[WorkflowQuestion]:
    families = _cell_family_counts(lib_doc)
    classes = _macro_class_counts(lef_doc)
    size_range = _macro_size_range(lef_doc)
    cross = _sdc_reference_matches(sdc_doc, lef_doc, lib_doc)
    clock_chunks = [chunk for chunk in sdc_doc.chunks if chunk.kind == "clock"]
    clock = clock_chunks[0]

    return [
        WorkflowQuestion(
            id="q1_clock",
            question="What clocks exist in this design?",
            answer=(
                f"1 clock from {clock.metadata.get('ports')} "
                f"with period {clock.metadata.get('period')} ns."
            ),
            evidence={
                "clock_count": sdc_doc.metadata["clock_count"],
                "period": clock.metadata.get("period"),
                "ports": clock.metadata.get("ports"),
            },
        ),
        WorkflowQuestion(
            id="q2_cells",
            question="What standard cells are characterized in the Liberty library?",
            answer=(
                f"{lib_doc.metadata['cell_count']} cells across {len(families)} families. "
                "Top families: "
                + ", ".join(f"{name} x{count}" for name, count in families.most_common(5))
                + "."
            ),
            evidence={
                "cell_count": lib_doc.metadata["cell_count"],
                "total_pin_count": lib_doc.metadata["total_pin_count"],
                "family_count": len(families),
                "top_families": dict(families.most_common(5)),
            },
        ),
        WorkflowQuestion(
            id="q3_macros",
            question="What physical macros exist in the LEF?",
            answer=(
                f"{lef_doc.metadata['macro_count']} macros. "
                f"Class distribution: {dict(classes)}. "
                f"Smallest width x height: {size_range['smallest']['width']} x "
                f"{size_range['smallest']['height']}; largest: "
                f"{size_range['largest']['width']} x {size_range['largest']['height']}."
            ),
            evidence={
                "macro_count": lef_doc.metadata["macro_count"],
                "classes": dict(classes),
                "size_range": size_range,
            },
        ),
        WorkflowQuestion(
            id="q4_pvt",
            question="What PVT corner is this Liberty characterized for?",
            answer=(
                f"{lib_doc.metadata['default_operating_conditions']}: "
                f"process {lib_doc.metadata['nom_process']}, "
                f"{lib_doc.metadata['nom_temperature']} C, "
                f"{lib_doc.metadata['nom_voltage']} V, "
                f"{lib_doc.metadata['delay_model']} delay model."
            ),
            evidence={
                "operating_conditions": lib_doc.metadata["default_operating_conditions"],
                "nom_process": lib_doc.metadata["nom_process"],
                "nom_voltage": lib_doc.metadata["nom_voltage"],
                "nom_temperature": lib_doc.metadata["nom_temperature"],
                "delay_model": lib_doc.metadata["delay_model"],
            },
        ),
        WorkflowQuestion(
            id="q5_cross_doc",
            question="Do SDC constraint targets reference Liberty cells or LEF macros?",
            answer=(
                "No direct cell or macro matches. This is expected because the gcd SDC "
                "names design-level ports, not library cells."
            ),
            evidence=cross,
        ),
    ]


def run_open_corpus_testbench(
    repo_root: str | Path,
    *,
    max_parse_seconds: float = 10.0,
) -> TestbenchReport:
    """Run the public workflow acceptance testbench.

    The corpus is intentionally small enough for CI but still real: SKY130
    Liberty + SKY130 merged LEF + a real gcd SDC.
    """
    root = Path(repo_root)
    paths = _fixture_paths(root)

    start = perf_counter()
    lib_doc = liberty.parse(paths["liberty"])
    lef_doc = lef.parse(paths["lef"])
    sdc_doc = sdc.parse(paths["sdc"])
    parse_seconds = perf_counter() - start

    total_chunks = sum(len(doc.chunks) for doc in (lib_doc, lef_doc, sdc_doc))
    chunk_kind_counts = _chunk_kind_counts(lib_doc, lef_doc, sdc_doc)
    class_counts = _macro_class_counts(lef_doc)
    families = _cell_family_counts(lib_doc)
    cross = _sdc_reference_matches(sdc_doc, lef_doc, lib_doc)
    questions = _build_questions(lib_doc, lef_doc, sdc_doc)
    clock = next(chunk for chunk in sdc_doc.chunks if chunk.kind == "clock")

    artifact_counts: dict[str, Any] = {
        "liberty_cells": lib_doc.metadata["cell_count"],
        "liberty_total_pins": lib_doc.metadata["total_pin_count"],
        "liberty_family_count": len(families),
        "lef_macros": lef_doc.metadata["macro_count"],
        "lef_macro_classes": dict(class_counts),
        "sdc_constraints": len(sdc_doc.chunks),
        "total_chunks": total_chunks,
        "chunk_kind_counts": dict(chunk_kind_counts),
    }
    checks = [
        _check_at_most(
            "parse all artifacts within ingest budget",
            parse_seconds,
            max_parse_seconds,
            "Cold parse of Liberty + merged LEF + SDC on the public fixture corpus.",
        ),
        _check("Liberty cell count", lib_doc.metadata["cell_count"], 428),
        _check("Liberty total pin count", lib_doc.metadata["total_pin_count"], 1771),
        _check("Liberty family count", len(families), 158),
        _check("Liberty PVT voltage", lib_doc.metadata["nom_voltage"], 1.8),
        _check("Liberty PVT temperature", lib_doc.metadata["nom_temperature"], 25.0),
        _check("LEF macro count", lef_doc.metadata["macro_count"], 441),
        _check(
            "LEF macro class distribution",
            dict(class_counts),
            {
                "BLOCK": 1,
                "CORE": 422,
                "CORE ANTENNACELL": 1,
                "CORE SPACER": 6,
                "CORE WELLTAP": 11,
            },
        ),
        _check("SDC clock count", sdc_doc.metadata["clock_count"], 1),
        _check("SDC input delay count", sdc_doc.metadata["input_delay_count"], 1),
        _check("SDC output delay count", sdc_doc.metadata["output_delay_count"], 1),
        _check("SDC input transition count", sdc_doc.metadata["input_transition_count"], 1),
        _check("SDC variable-resolved clock period", clock.metadata.get("period"), 5.0),
        _check("SDC clock source", clock.metadata.get("ports"), "[get_ports clk]"),
        _check("Retrieval chunk count", total_chunks, 873),
        _check(
            "Retrieval chunk kinds",
            dict(chunk_kind_counts),
            {
                "lef:macro": 441,
                "liberty:cell": 428,
                "sdc:clock": 1,
                "sdc:input_delay": 1,
                "sdc:input_transition": 1,
                "sdc:output_delay": 1,
            },
        ),
        _check(
            "Cross-document target matches",
            {
                "liberty_cell_matches": len(cross["liberty_cell_matches"]),
                "lef_macro_matches": len(cross["lef_macro_matches"]),
            },
            {"liberty_cell_matches": 0, "lef_macro_matches": 0},
            "Expected for gcd: SDC constraints target top-level design ports.",
        ),
    ]

    return TestbenchReport(
        corpus={name: str(path.relative_to(root)) for name, path in paths.items()},
        parse_seconds=parse_seconds,
        artifact_counts=artifact_counts,
        checks=checks,
        questions=questions,
    )


def render_text_report(report: TestbenchReport) -> str:
    """Render a compact terminal-friendly report."""
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"eda-parse open-corpus workflow testbench: {status}",
        f"parse_seconds: {report.parse_seconds:.4f}",
        "",
        "corpus:",
    ]
    for name, path in report.corpus.items():
        lines.append(f"  - {name}: {path}")
    lines.extend(["", "artifact_counts:"])
    for name, value in report.artifact_counts.items():
        lines.append(f"  - {name}: {value}")
    lines.extend(["", "checks:"])
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(f"  - [{marker}] {check.name}: observed={check.observed!r}, expected={check.expected!r}")
        if check.detail:
            lines.append(f"      {check.detail}")
    lines.extend(["", "workflow_questions:"])
    for question in report.questions:
        lines.append(f"  - {question.id}: {question.question}")
        lines.append(f"      {question.answer}")
    return "\n".join(lines)
