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

    assert [task.task_id for task in tasks] == [
        "physics_001_overconstrained_clock",
        "physics_002_missing_input_delay",
        "physics_003_unconstrained_paths",
    ]

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

