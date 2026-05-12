from __future__ import annotations

from pathlib import Path

from eda_parse.testbench import render_text_report, run_open_corpus_testbench


def test_open_corpus_testbench_passes() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    report = run_open_corpus_testbench(repo_root, max_parse_seconds=60.0)

    assert report.passed is True
    assert report.artifact_counts["liberty_cells"] == 428
    assert report.artifact_counts["lef_macros"] == 441
    assert report.artifact_counts["sdc_constraints"] == 4
    assert report.artifact_counts["total_chunks"] == 873
    assert len(report.questions) == 5


def test_open_corpus_testbench_report_is_serializable() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    report = run_open_corpus_testbench(repo_root, max_parse_seconds=60.0)
    payload = report.to_dict()
    text = render_text_report(report)

    assert payload["passed"] is True
    assert payload["checks"][0]["name"] == "parse all artifacts within ingest budget"
    assert "workflow testbench: PASS" in text
    assert "Q" not in text

