from __future__ import annotations

from pathlib import Path

from benchmarks.timing_diagnosis.harness import grade_submission, iter_tasks, validate_task

TASKS_ROOT = (
    Path(__file__).resolve().parent.parent
    / "benchmarks"
    / "timing_diagnosis"
    / "tasks"
)


def test_timing_diagnosis_tasks_validate() -> None:
    tasks = iter_tasks(TASKS_ROOT)
    task_ids = {task.task_id for task in tasks}

    # The three first-principles physics seeds must always be present —
    # they're the harness fixtures.
    required_seeds = {
        "physics_001_overconstrained_clock",
        "physics_002_missing_input_delay",
        "physics_003_unconstrained_paths",
    }
    assert required_seeds.issubset(task_ids), (
        f"missing physics seeds: {sorted(required_seeds - task_ids)}"
    )

    # Every loaded task must validate structurally — covers physics seeds,
    # external_authority cases, and any future external_tool cases.
    for task in tasks:
        checks = validate_task(task)
        assert all(check.passed for check in checks), [
            check for check in checks if not check.passed
        ]


def test_grader_accepts_correct_overconstrained_clock_answer() -> None:
    report = grade_submission(
        TASKS_ROOT / "physics_001_overconstrained_clock",
        {
            "failing_stage": "static_timing",
            "violation_type": "setup",
            "root_cause": "clock_period_too_short",
            "clock": "core_clk",
            "declared_period_ns": 1.0,
            "worst_slack_ns": -0.42,
            "minimum_passing_period_ns": 1.42,
            "evidence": [
                "input/constraints.sdc:1",
                "input/reports/timing_report.rpt:24",
            ],
            "next_action": "Relax the core_clk period to at least 1.42 ns.",
            "confidence": 0.84,
        },
    )

    assert report.passed is True
    assert report.score == 1.0


def test_grader_rejects_plausible_but_wrong_diagnosis() -> None:
    report = grade_submission(
        TASKS_ROOT / "physics_001_overconstrained_clock",
        {
            "failing_stage": "static_timing",
            "violation_type": "hold",
            "root_cause": "missing_false_path",
            "clock": "core_clk",
            "declared_period_ns": 1.0,
            "worst_slack_ns": 0.42,
            "minimum_passing_period_ns": 1.0,
            "evidence": ["input/reports/timing_report.rpt:24"],
            "next_action": "Add a false path exception.",
            "confidence": 0.72,
        },
    )

    failed_names = {check.name for check in report.checks if not check.passed}
    assert report.passed is False
    assert "exact:violation_type" in failed_names
    assert "exact:root_cause" in failed_names
    assert "numeric:worst_slack_ns" in failed_names
    assert "evidence:constraints.sdc" in failed_names
    assert "next_action:relax" in failed_names


def test_grader_accepts_missing_input_delay_answer() -> None:
    report = grade_submission(
        TASKS_ROOT / "physics_002_missing_input_delay",
        {
            "failing_stage": "constraint_check",
            "violation_type": "constraint_coverage",
            "root_cause": "missing_input_delay",
            "clock": "core_clk",
            "declared_period_ns": 5.0,
            "unconstrained_input_count": 5,
            "evidence": [
                "input/constraints.sdc:1-4",
                "input/reports/timing_report.rpt:4-9",
            ],
            "next_action": "Add set_input_delay constraints relative to core_clk.",
            "confidence": 0.88,
        },
    )

    assert report.passed is True


def test_grader_accepts_clock_port_mismatch_answer() -> None:
    report = grade_submission(
        TASKS_ROOT / "physics_003_unconstrained_paths",
        {
            "failing_stage": "constraint_check",
            "violation_type": "unconstrained_paths",
            "root_cause": "clock_target_mismatch",
            "clock": "core_clk",
            "declared_period_ns": 2.0,
            "evidence": [
                "input/design.v:2",
                "input/constraints.sdc:1",
                "input/reports/timing_report.rpt:4",
            ],
            "next_action": "Change the create_clock target from clk_core to clk.",
            "confidence": 0.9,
        },
    )

    assert report.passed is True


def test_grader_resolves_cited_evidence_line_content() -> None:
    report = grade_submission(
        TASKS_ROOT / "authority_001_ol_1371_hold_repair_setup_conflict",
        {
            "failing_stage": "static_timing",
            "violation_type": "hold",
            "root_cause": "hold_repair_blocked_by_setup_margin_guard",
            "evidence": ["input/16-resizer.log:104"],
            "next_action": "Set GLB_RESIZER_ALLOW_SETUP_VIOS=1 for the hold repair pass.",
            "confidence": 0.86,
        },
    )

    assert report.passed is True
    assert report.score == 1.0


def test_grader_accepts_nearby_cited_evidence_line_content() -> None:
    report = grade_submission(
        TASKS_ROOT / "authority_002_ol_958_report_clock_skew_feedback_loop",
        {
            "failing_stage": "static_timing",
            "violation_type": "other",
            "root_cause": "opensta_report_clock_skew_combinational_feedback_loop_hang",
            "evidence": [
                "input/standalone/sta_clock_skew_excerpt.tcl:7",
                "input/thread_excerpt.md:35",
            ],
            "next_action": "Use the OpenROAD e3315ba41 fix.",
            "confidence": 0.86,
        },
    )

    assert report.passed is True
    assert report.score == 1.0


def test_authority_root_cause_accepts_token_paraphrase() -> None:
    report = grade_submission(
        TASKS_ROOT / "authority_003_or_4833_report_metrics_bottleneck",
        {
            "failing_stage": "global_route",
            "violation_type": "other",
            "root_cause": "report_metrics_dominates_grt_runtime",
            "evidence": [
                "input/logs/5_1_grt.tmp.log:61",
                "input/scripts/global_route_tail.tcl:12",
            ],
            "next_action": "Set SKIP_REPORT_METRICS=1 for the immediate rerun.",
            "confidence": 0.86,
        },
    )

    assert report.passed is True
    assert report.score == 1.0
