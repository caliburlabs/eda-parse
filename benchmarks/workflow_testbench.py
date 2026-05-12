#!/usr/bin/env python3
"""Run the public eda-parse workflow testbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eda_parse.testbench import render_text_report, run_open_corpus_testbench


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root containing tests/fixtures.",
    )
    parser.add_argument(
        "--max-parse-seconds",
        type=float,
        default=10.0,
        help="Fail if the public corpus takes longer than this to parse.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write the full report as JSON to this path.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only JSON to stdout.",
    )
    args = parser.parse_args()

    report = run_open_corpus_testbench(
        args.repo_root,
        max_parse_seconds=args.max_parse_seconds,
    )
    payload = report.to_dict()

    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.json_only:
        print(json.dumps(payload, indent=2))
    else:
        print(render_text_report(report))

    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()

