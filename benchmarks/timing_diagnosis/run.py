#!/usr/bin/env python3
"""CLI for the timing-diagnosis benchmark harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from benchmarks.timing_diagnosis.harness import (
    grade_submission,
    iter_tasks,
    render_grade_report,
    validate_task,
)

DEFAULT_TASKS_ROOT = Path(__file__).resolve().parent / "tasks"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List timing-diagnosis tasks.")
    list_parser.add_argument("--tasks-root", type=Path, default=DEFAULT_TASKS_ROOT)

    validate_parser = subparsers.add_parser("validate", help="Validate task bundle structure.")
    validate_parser.add_argument("--tasks-root", type=Path, default=DEFAULT_TASKS_ROOT)

    grade_parser = subparsers.add_parser("grade", help="Grade one agent JSON submission.")
    grade_parser.add_argument("task_root", type=Path)
    grade_parser.add_argument("submission", type=Path)
    grade_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    args = parser.parse_args()

    if args.command == "list":
        for task in iter_tasks(args.tasks_root):
            print(f"{task.task_id}\t{task.oracle_type}\t{task.oracle_status}\t{task.title}")
        return

    if args.command == "validate":
        failed = False
        for task in iter_tasks(args.tasks_root):
            checks = validate_task(task)
            task_failed = not all(check.passed for check in checks)
            failed = failed or task_failed
            marker = "FAIL" if task_failed else "PASS"
            print(f"{marker} {task.task_id}")
            for check in checks:
                check_marker = "PASS" if check.passed else "FAIL"
                print(f"  - [{check_marker}] {check.name}")
        raise SystemExit(1 if failed else 0)

    if args.command == "grade":
        report = grade_submission(args.task_root, args.submission)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(render_grade_report(report))
        raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()

