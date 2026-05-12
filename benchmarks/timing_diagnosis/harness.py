"""Timing-diagnosis benchmark harness.

The harness deliberately separates the files an agent may inspect from the
golden oracle used by the grader:

* ``input/`` and ``prompt.md`` are visible to the agent.
* ``hidden_oracle/golden.json`` is not visible to the agent.

The same grading code handles first-principles physics tasks, tool-generated
OpenSTA/PrimeTime tasks, and sealed authority tasks written by a human oracle.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FieldCheck:
    """One graded assertion against an agent answer."""

    name: str
    passed: bool
    observed: Any
    expected: Any
    detail: str = ""


@dataclass(frozen=True)
class GradeReport:
    """Result of grading one timing-diagnosis answer."""

    task_id: str
    oracle_type: str
    oracle_status: str
    passed: bool
    score: float
    checks: list[FieldCheck]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TimingDiagnosisTask:
    """A frozen timing-diagnosis task bundle."""

    task_id: str
    title: str
    root: Path
    prompt_path: Path
    golden_path: Path
    input_artifacts: list[Path]
    oracle_type: str
    oracle_status: str

    def prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def golden(self) -> dict[str, Any]:
        return _read_json(self.golden_path)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def load_task(task_root: str | Path) -> TimingDiagnosisTask:
    """Load one task directory."""
    root = Path(task_root)
    manifest = _read_json(root / "task.json")
    prompt_path = root / str(manifest.get("prompt", "prompt.md"))
    golden_path = root / str(manifest.get("golden", "hidden_oracle/golden.json"))
    artifacts = [
        root / str(path)
        for path in manifest.get("input_artifacts", [])
        if isinstance(path, str)
    ]

    return TimingDiagnosisTask(
        task_id=str(manifest["task_id"]),
        title=str(manifest["title"]),
        root=root,
        prompt_path=prompt_path,
        golden_path=golden_path,
        input_artifacts=artifacts,
        oracle_type=str(manifest["oracle_type"]),
        oracle_status=str(manifest["oracle_status"]),
    )


def iter_tasks(tasks_root: str | Path) -> list[TimingDiagnosisTask]:
    """Load all task bundles under ``tasks_root``."""
    root = Path(tasks_root)
    tasks: list[TimingDiagnosisTask] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "task.json").exists():
            tasks.append(load_task(child))
    return tasks


def validate_task(task: TimingDiagnosisTask) -> list[FieldCheck]:
    """Validate that a task bundle is structurally complete."""
    checks = [
        FieldCheck("prompt exists", task.prompt_path.exists(), str(task.prompt_path), "existing file"),
        FieldCheck("golden exists", task.golden_path.exists(), str(task.golden_path), "existing file"),
    ]
    checks.extend(
        FieldCheck(
            f"input artifact exists: {path.relative_to(task.root)}",
            path.exists(),
            str(path),
            "existing file",
        )
        for path in task.input_artifacts
    )

    if task.golden_path.exists():
        golden = task.golden()
        checks.append(
            FieldCheck(
                "task id matches golden",
                golden.get("task_id") == task.task_id,
                golden.get("task_id"),
                task.task_id,
            )
        )
        checks.append(
            FieldCheck(
                "oracle type matches golden",
                golden.get("oracle_type") == task.oracle_type,
                golden.get("oracle_type"),
                task.oracle_type,
            )
        )

    return checks


def grade_submission(
    task_root: str | Path,
    submission: str | Path | dict[str, Any],
) -> GradeReport:
    """Grade one agent submission against a hidden golden answer.

    ``submission`` may be a JSON file path or an already-loaded mapping.
    """
    task = load_task(task_root)
    payload = _read_json(Path(submission)) if isinstance(submission, (str, Path)) else submission
    return grade_payload(task, payload)


def grade_payload(task: TimingDiagnosisTask, payload: dict[str, Any]) -> GradeReport:
    """Grade an already-loaded agent answer."""
    golden = task.golden()
    checks: list[FieldCheck] = []

    checks.extend(_grade_exact_fields(golden, payload))
    checks.extend(_grade_numeric_fields(golden, payload))
    checks.extend(_grade_evidence(golden, payload))
    checks.extend(_grade_next_action_terms(golden, payload))

    passed_count = sum(1 for check in checks if check.passed)
    score = passed_count / len(checks) if checks else 0.0
    return GradeReport(
        task_id=task.task_id,
        oracle_type=task.oracle_type,
        oracle_status=task.oracle_status,
        passed=all(check.passed for check in checks),
        score=round(score, 4),
        checks=checks,
    )


def _grade_exact_fields(golden: dict[str, Any], payload: dict[str, Any]) -> list[FieldCheck]:
    checks: list[FieldCheck] = []
    required = golden.get("required_exact", {})
    if not isinstance(required, dict):
        raise ValueError("golden.required_exact must be an object")

    for field, expected in required.items():
        observed = payload.get(field)
        checks.append(
            FieldCheck(
                f"exact:{field}",
                _matches_expected(observed, expected),
                observed,
                expected,
            )
        )
    return checks


def _grade_numeric_fields(golden: dict[str, Any], payload: dict[str, Any]) -> list[FieldCheck]:
    checks: list[FieldCheck] = []
    required = golden.get("required_numeric", {})
    if not isinstance(required, dict):
        raise ValueError("golden.required_numeric must be an object")

    for field, spec in required.items():
        if not isinstance(spec, dict):
            raise ValueError(f"golden.required_numeric.{field} must be an object")
        expected = float(spec["value"])
        tolerance = float(spec.get("tolerance", 0.0))
        observed_raw = payload.get(field)
        observed = _coerce_float(observed_raw)
        passed = observed is not None and abs(observed - expected) <= tolerance
        checks.append(
            FieldCheck(
                f"numeric:{field}",
                passed,
                observed_raw,
                {"value": expected, "tolerance": tolerance},
            )
        )
    return checks


def _grade_evidence(golden: dict[str, Any], payload: dict[str, Any]) -> list[FieldCheck]:
    evidence = payload.get("evidence", [])
    if isinstance(evidence, str):
        evidence_items = [evidence]
    elif isinstance(evidence, list):
        evidence_items = [str(item) for item in evidence]
    else:
        evidence_items = []
    evidence_text = "\n".join(evidence_items).lower()

    checks: list[FieldCheck] = []
    for token in golden.get("required_evidence", []):
        token_text = str(token).lower()
        checks.append(
            FieldCheck(
                f"evidence:{token}",
                token_text in evidence_text,
                evidence_items,
                f"contains {token}",
            )
        )
    return checks


def _grade_next_action_terms(golden: dict[str, Any], payload: dict[str, Any]) -> list[FieldCheck]:
    next_action = str(payload.get("next_action", "")).lower()
    checks: list[FieldCheck] = []
    for term in golden.get("required_next_action_terms", []):
        term_text = str(term).lower()
        checks.append(
            FieldCheck(
                f"next_action:{term}",
                term_text in next_action,
                payload.get("next_action", ""),
                f"contains {term}",
            )
        )
    return checks


def _matches_expected(observed: Any, expected: Any) -> bool:
    candidates = expected if isinstance(expected, list) else [expected]
    return any(_normalise(observed) == _normalise(candidate) for candidate in candidates)


def _normalise(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.lower().strip().split())
    return value


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def render_grade_report(report: GradeReport) -> str:
    """Render a compact terminal report."""
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"timing diagnosis task {report.task_id}: {status}",
        f"oracle: {report.oracle_type} ({report.oracle_status})",
        f"score: {report.score:.2%}",
        "",
        "checks:",
    ]
    for check in report.checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(
            f"  - [{marker}] {check.name}: observed={check.observed!r}, expected={check.expected!r}"
        )
    return "\n".join(lines)
