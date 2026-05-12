"""Tests for the timing-diagnosis agent harness.

These tests deliberately avoid the Anthropic API: every model interaction
is replayed via :class:`MockClient`. They cover three properties:

1. The path sandbox refuses access outside ``input/`` (so the agent cannot
   reach ``hidden_oracle/`` through any tool).
2. A scripted multi-turn run that ends with ``final_answer`` produces an
   answer dict the grader can score, and the answer round-trips through
   the grader to PASS against the matching golden.
3. Loops that exhaust ``max_iters`` without ``final_answer`` return a stub
   answer (instead of crashing) so the grader still produces a report.
4. Tool errors surface to the model as ``is_error`` tool_results rather
   than tearing down the loop.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from benchmarks.timing_diagnosis import harness
from benchmarks.timing_diagnosis.agent import (
    MockClient,
    PathSandboxError,
    _safe_input_path,
    _tool_grep,
    _tool_list_dir,
    _tool_parse_sdc,
    _tool_read_file,
    run_agent,
)

TASKS_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "timing_diagnosis" / "tasks"


# ----------------------------------------------------------------------
# Sandbox
# ----------------------------------------------------------------------


def test_safe_input_path_resolves_simple_relative() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    resolved = _safe_input_path(task, "constraints.sdc")
    assert resolved == (task / "input" / "constraints.sdc").resolve()


def test_safe_input_path_accepts_input_prefix() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    resolved = _safe_input_path(task, "input/constraints.sdc")
    assert resolved == (task / "input" / "constraints.sdc").resolve()


def test_safe_input_path_rejects_traversal() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    with pytest.raises(PathSandboxError):
        _safe_input_path(task, "../hidden_oracle/golden.json")


def test_safe_input_path_rejects_absolute_outside() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    with pytest.raises(PathSandboxError):
        _safe_input_path(task, "/etc/passwd")


def test_safe_input_path_rejects_hidden_oracle_via_input_prefix() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    with pytest.raises(PathSandboxError):
        _safe_input_path(task, "input/../hidden_oracle/golden.json")


def test_read_file_returns_sdc_contents() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    text = _tool_read_file(task, path="constraints.sdc")
    assert "1: create_clock" in text


def test_list_dir_shows_reports_subdir() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    listing = _tool_list_dir(task, path="")
    assert "input/constraints.sdc" in listing
    # reports/ is a subdir on this task
    assert "input/reports/" in listing


def test_grep_finds_pattern_in_input() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    matches = _tool_grep(task, pattern=r"create_clock", path="constraints.sdc")
    assert "create_clock" in matches
    assert "input/constraints.sdc:" in matches


def test_parse_sdc_via_tool_resolves_variables() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    summary = _tool_parse_sdc(task, path="constraints.sdc")
    # The physics_001 SDC declares one clock, so the structured summary
    # should reflect that.
    assert '"clock_count": 1' in summary


# ----------------------------------------------------------------------
# End-to-end scripted run
# ----------------------------------------------------------------------


def _golden_payload_script(task_id: str, payload: dict) -> list[list[dict]]:
    """Build a minimal scripted-mock conversation:

    Turn 1: model lists the input directory (one tool call) — exercises a
    real tool round-trip so the loop and tool_use_id correlation are
    actually tested rather than skipped.

    Turn 2: model commits ``final_answer`` with the supplied payload.
    """
    return [
        [
            {"type": "text", "text": "Let me see what's in input/."},
            {
                "type": "tool_use",
                "id": "toolu_list",
                "name": "list_dir",
                "input": {"path": ""},
            },
        ],
        [
            {"type": "text", "text": f"Submitting diagnosis for {task_id}."},
            {
                "type": "tool_use",
                "id": "toolu_final",
                "name": "final_answer",
                "input": payload,
            },
        ],
    ]


def _golden_answer_for_physics_001() -> dict:
    # Matches the golden for physics_001_overconstrained_clock.
    return {
        "failing_stage": "static_timing",
        "violation_type": "setup",
        "root_cause": "clock_period_too_short",
        "clock": "core_clk",
        "declared_period_ns": 1.0,
        "worst_slack_ns": -0.42,
        "minimum_passing_period_ns": 1.42,
        "evidence": [
            "input/constraints.sdc:3",
            "input/reports/timing_report.rpt:26",
        ],
        "next_action": "Relax the core_clk period to at least 1.42 ns to give the critical path slack.",
        "confidence": 0.9,
    }


def test_run_agent_with_mock_completes_and_passes_grader() -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    script = _golden_payload_script(
        "physics_001_overconstrained_clock", _golden_answer_for_physics_001()
    )
    client = MockClient(script=script)
    result = run_agent(task, client=client, max_iters=5)

    assert result.completed, result.reason
    assert result.turns == 2

    # The answer should grade as PASS against the matching golden.
    report = harness.grade_payload(harness.load_task(task), result.answer)
    assert report.passed, harness.render_grade_report(report)


def test_run_agent_flattens_additional_fields() -> None:
    """`additional_fields` should be hoisted to the top level of the answer
    so the grader can compare task-specific extras like
    `unconstrained_input_count` directly.
    """
    task = TASKS_ROOT / "physics_003_unconstrained_paths"
    golden = harness.load_task(task).golden()
    # Build an answer that satisfies the required_exact/required_numeric of
    # this task's golden, with any extra numeric requirements packed into
    # additional_fields.
    payload: dict = {
        "failing_stage": next(iter(_as_list(golden["required_exact"]["failing_stage"]))),
        "violation_type": next(iter(_as_list(golden["required_exact"]["violation_type"]))),
        "root_cause": next(iter(_as_list(golden["required_exact"]["root_cause"]))),
        "evidence": [tok for tok in golden.get("required_evidence", [])],
        "next_action": " ".join(
            f"{term}" for term in golden.get("required_next_action_terms", [])
        )
        or "n/a",
        "confidence": 0.5,
    }
    # Numeric fields: half land at top level, half under additional_fields,
    # to prove the flattener moves them up. We split by sorted key for
    # determinism.
    numeric = golden.get("required_numeric", {}) or {}
    keys = sorted(numeric.keys())
    additional: dict = {}
    for i, k in enumerate(keys):
        spec = numeric[k]
        if i % 2 == 0:
            payload[k] = spec["value"]
        else:
            additional[k] = spec["value"]
    if additional:
        payload["additional_fields"] = additional

    script = [
        [
            {
                "type": "tool_use",
                "id": "toolu_final",
                "name": "final_answer",
                "input": payload,
            }
        ]
    ]
    client = MockClient(script=script)
    result = run_agent(task, client=client, max_iters=2)

    assert result.completed, result.reason
    # additional_fields itself should not survive flattening.
    assert "additional_fields" not in result.answer
    for k in keys:
        assert k in result.answer, f"missing flattened field {k!r}"


def _as_list(value):
    return value if isinstance(value, list) else [value]


# ----------------------------------------------------------------------
# Loop exhaustion + error surfaces
# ----------------------------------------------------------------------


def test_run_agent_returns_stub_when_max_iters_exhausts() -> None:
    """Model just keeps calling list_dir forever — the loop should bail
    cleanly with a stub answer rather than crashing.
    """
    task = TASKS_ROOT / "physics_001_overconstrained_clock"

    def _idle_turn(i: int) -> list[dict]:
        return [
            {
                "type": "tool_use",
                "id": f"toolu_{i}",
                "name": "list_dir",
                "input": {"path": ""},
            }
        ]

    script = [_idle_turn(i) for i in range(10)]
    client = MockClient(script=script)
    result = run_agent(task, client=client, max_iters=3)

    assert not result.completed
    assert result.answer["root_cause"] == "no_final_answer"
    assert result.answer["failing_stage"] == "unknown"
    assert "agent did not commit" in result.answer["next_action"]


def test_run_agent_recovers_from_invalid_tool_args() -> None:
    """A bad tool call should come back to the model as is_error=True
    instead of tearing down the loop.
    """
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    script = [
        # Turn 1: bogus path — sandbox should reject.
        [
            {
                "type": "tool_use",
                "id": "toolu_bad",
                "name": "read_file",
                "input": {"path": "../../hidden_oracle/golden.json"},
            }
        ],
        # Turn 2: recover with a final answer.
        [
            {
                "type": "tool_use",
                "id": "toolu_final",
                "name": "final_answer",
                "input": _golden_answer_for_physics_001(),
            }
        ],
    ]
    client = MockClient(script=script)
    result = run_agent(task, client=client, max_iters=5)

    assert result.completed
    # The bad call should not have corrupted the final answer.
    assert result.answer["root_cause"] == "clock_period_too_short"


def test_run_agent_writes_transcript(tmp_path) -> None:
    task = TASKS_ROOT / "physics_001_overconstrained_clock"
    transcript = tmp_path / "run.jsonl"
    script = _golden_payload_script(
        "physics_001_overconstrained_clock", _golden_answer_for_physics_001()
    )
    client = MockClient(script=script)
    run_agent(task, client=client, max_iters=5, transcript_path=transcript)

    lines = transcript.read_text(encoding="utf-8").strip().splitlines()
    # At minimum: 1 user prompt + 2 assistant turns + 1 list_dir tool result
    # + 1 final_answer record.
    assert len(lines) >= 5
    assert any('"kind": "user"' in line for line in lines)
    assert any('"kind": "assistant"' in line for line in lines)
    assert any('"kind": "final_answer"' in line for line in lines)
