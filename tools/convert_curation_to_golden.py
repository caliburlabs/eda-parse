#!/usr/bin/env python3
"""Convert rich authority-case curation dumps into bench oracle artifacts."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

_CASE_BLOCK_RE = re.compile(
    r"^### tasks/(?P<header_case_id>[^/\n]+)/hidden_oracle/golden\.json[^\n]*\s*"
    r"```json\s*(?P<body>\{.*?\})\s*```",
    re.MULTILINE | re.DOTALL,
)

_PROVENANCE_KEYS = (
    "state",
    "state_evidence",
    "category",
    "difficulty",
    "tier",
    "fix_commit",
    "fix_pr",
    "fix_file_path",
    "fix_repo",
    "fix_action",
    "breaking_commit",
    "breaking_pr",
    "user_workaround",
    "underlying_recommendation",
    "actual_bottleneck",
    "tool_that_missed_it",
    "audited_file",
    "specific_line",
)


@dataclass(frozen=True)
class ConversionResult:
    """One generated oracle artifact pair."""

    case_id: str
    task_id: str
    golden_path: Path
    provenance_path: Path


def load_curation_cases(path: Path) -> dict[str, JsonObject]:
    """Load rich curation cases from markdown fences or raw JSON."""
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return _cases_from_json(json.loads(text))
    return extract_cases_from_markdown(text)


def extract_cases_from_markdown(text: str) -> dict[str, JsonObject]:
    """Extract research-Claude JSON case blocks from a markdown dump."""
    cases: dict[str, JsonObject] = {}
    for match in _CASE_BLOCK_RE.finditer(text):
        header_case_id = match.group("header_case_id")
        payload = _as_object(json.loads(match.group("body")), f"case {header_case_id}")
        case_id = _required_str(payload.get("case_id"), f"case {header_case_id}.case_id")
        if case_id != header_case_id:
            raise ValueError(
                f"Case heading {header_case_id!r} disagrees with payload case_id {case_id!r}"
            )
        if case_id in cases:
            raise ValueError(f"Duplicate rich curation case {case_id!r}")
        cases[case_id] = payload

    if not cases:
        raise ValueError("No `tasks/<case>/hidden_oracle/golden.json` JSON blocks found")
    return cases


def load_overlay(path: Path) -> dict[str, JsonObject]:
    """Load grader overlays keyed by rich `case_id`."""
    payload = _as_object(json.loads(path.read_text(encoding="utf-8")), "overlay root")
    raw_cases = payload.get("cases", payload)
    overlay_cases = _as_object(raw_cases, "overlay cases")
    overlays: dict[str, JsonObject] = {}
    for case_id, raw_overlay in overlay_cases.items():
        overlay = _as_object(raw_overlay, f"overlay for {case_id}")
        overlays[str(case_id)] = overlay
    return overlays


def build_golden(rich_case: Mapping[str, Any], overlay: Mapping[str, Any]) -> JsonObject:
    """Build one grader-compatible `golden.json` document."""
    case_id = _required_str(rich_case.get("case_id"), "rich case.case_id")
    task_id = _required_str(overlay.get("task_id"), f"overlay {case_id}.task_id")
    oracle_type = _required_str(overlay.get("oracle_type", "external_authority"), "oracle_type")
    if oracle_type not in {"physics_first_principles", "external_tool", "external_authority"}:
        raise ValueError(f"Unsupported oracle_type {oracle_type!r}")

    provenance_overlay = _optional_object(
        overlay.get("provenance"),
        f"overlay {case_id}.provenance",
    )
    provenance = _build_provenance(rich_case, provenance_overlay)

    return {
        "task_id": task_id,
        "oracle_type": oracle_type,
        "provenance": provenance,
        "required_exact": _required_object(
            overlay.get("required_exact"),
            f"overlay {case_id}.required_exact",
        ),
        "required_numeric": _required_object(
            overlay.get("required_numeric"),
            f"overlay {case_id}.required_numeric",
        ),
        "required_evidence": _required_string_list(
            overlay.get("required_evidence"),
            f"overlay {case_id}.required_evidence",
        ),
        "required_next_action_terms": _required_string_list(
            overlay.get("required_next_action_terms"),
            f"overlay {case_id}.required_next_action_terms",
        ),
    }


def render_provenance_markdown(
    rich_case: Mapping[str, Any],
    *,
    task_id: str,
    provenance_overlay: Mapping[str, Any] | None = None,
) -> str:
    """Render the human-auditable provenance companion."""
    case_id = _required_str(rich_case.get("case_id"), "rich case.case_id")
    display_case = dict(rich_case)
    if provenance_overlay:
        display_case.update(provenance_overlay)
    source_url = _optional_str(display_case.get("source_url"))
    state = _optional_str(display_case.get("state"))
    state_evidence = _optional_str(display_case.get("state_evidence"))
    category = _optional_str(display_case.get("category"))
    difficulty = _optional_str(display_case.get("difficulty"))
    tier = display_case.get("tier")

    lines = [
        f"# Provenance - {task_id}",
        "",
        "Generated from the rich external-authority curation payload. The grader-facing",
        "`golden.json` is derived from an explicit overlay; this file preserves the",
        "human-auditable quote trail and the richer case notes.",
        "",
        "## Source",
        "",
        f"- Rich case id: `{case_id}`",
    ]
    _append_optional_bullet(lines, "URL", source_url)
    _append_optional_bullet(lines, "State", state)
    _append_optional_bullet(lines, "State evidence", state_evidence)
    _append_optional_bullet(lines, "Category", category)
    _append_optional_bullet(lines, "Difficulty", difficulty)
    if tier is not None:
        lines.append(f"- Tier: `{tier}`")

    diagnoses = _required_list(rich_case.get("verbatim_diagnoses", []), "verbatim_diagnoses")
    lines.extend(["", "## Verbatim diagnoses", ""])
    if diagnoses:
        for diagnosis in diagnoses:
            entry = _as_object(diagnosis, "verbatim diagnosis")
            author = _optional_str(entry.get("author")) or "unknown author"
            name = _optional_str(entry.get("author_name"))
            role = _optional_str(entry.get("role"))
            source = _optional_str(entry.get("source"))
            label_parts = [part for part in (name, role) if part]
            author_label = f"**{author}**"
            if label_parts:
                author_label += f" ({' - '.join(label_parts)})"
            lines.extend([f"> {author_label}:", ">"])
            lines.extend(_quote_block(_required_str(entry.get("quote"), "diagnosis quote")))
            if source:
                lines.extend([">", f"> Source: {source}"])
            lines.append("")
    else:
        lines.extend(["No verbatim diagnoses recorded.", ""])

    metadata_lines = _render_known_metadata(display_case)
    if metadata_lines:
        lines.extend(["## Resolution metadata", "", *metadata_lines, ""])

    artifact_lines = _render_artifact_references(rich_case)
    if artifact_lines:
        lines.extend(["## Artifact references from curation", "", *artifact_lines, ""])

    grading_notes = _required_list(rich_case.get("grading_rubric", []), "grading_rubric")
    if grading_notes:
        lines.extend(["## Human grading notes from curation", ""])
        lines.extend(f"- {item!s}" for item in grading_notes)
        lines.append("")

    lines.extend(
        [
            "## Raw curation payload",
            "",
            "```json",
            json.dumps(dict(rich_case), indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def convert_cases(
    cases: Mapping[str, Mapping[str, Any]],
    overlays: Mapping[str, Mapping[str, Any]],
    *,
    tasks_root: Path,
    selected_case_ids: Iterable[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[ConversionResult]:
    """Convert selected rich cases into bench hidden-oracle artifacts."""
    selected = sorted(set(selected_case_ids or cases.keys()))
    unknown_selected = [case_id for case_id in selected if case_id not in cases]
    if unknown_selected:
        raise ValueError(f"Unknown rich curation case(s): {', '.join(unknown_selected)}")

    unused_overlay_keys = sorted(set(overlays) - set(cases))
    if unused_overlay_keys:
        raise ValueError(f"Overlay references unknown case(s): {', '.join(unused_overlay_keys)}")

    results: list[ConversionResult] = []
    for case_id in selected:
        overlay = overlays.get(case_id)
        if overlay is None:
            raise ValueError(f"Missing grader overlay for rich case {case_id!r}")
        rich_case = cases[case_id]
        golden = build_golden(rich_case, overlay)
        task_id = _required_str(golden.get("task_id"), f"golden {case_id}.task_id")
        hidden_oracle_dir = tasks_root / task_id / "hidden_oracle"
        golden_path = hidden_oracle_dir / "golden.json"
        provenance_path = hidden_oracle_dir / "provenance.md"

        if not dry_run:
            hidden_oracle_dir.mkdir(parents=True, exist_ok=True)
            if not force:
                existing = [path for path in (golden_path, provenance_path) if path.exists()]
                if existing:
                    paths = ", ".join(str(path) for path in existing)
                    raise FileExistsError(f"Refusing to overwrite existing output(s): {paths}")
            golden_path.write_text(
                f"{json.dumps(golden, indent=2)}\n",
                encoding="utf-8",
            )
            provenance_path.write_text(
                render_provenance_markdown(
                    rich_case,
                    task_id=task_id,
                    provenance_overlay=_optional_object(
                        overlay.get("provenance"),
                        f"overlay {case_id}.provenance",
                    ),
                ),
                encoding="utf-8",
            )

        results.append(
            ConversionResult(
                case_id=case_id,
                task_id=task_id,
                golden_path=golden_path,
                provenance_path=provenance_path,
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curation", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        help="Convert only the named rich case id. May be repeated.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cases = load_curation_cases(args.curation)
    overlays = load_overlay(args.overlay)
    results = convert_cases(
        cases,
        overlays,
        tasks_root=args.tasks_root,
        selected_case_ids=args.case_ids,
        dry_run=args.dry_run,
        force=args.force,
    )
    action = "would write" if args.dry_run else "wrote"
    for result in results:
        print(
            f"{action} {result.case_id} -> {result.golden_path} and {result.provenance_path}"
        )


def _cases_from_json(payload: Any) -> dict[str, JsonObject]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and "cases" in payload:
        cases = payload["cases"]
        if isinstance(cases, dict):
            items = list(cases.values())
        else:
            items = _required_list(cases, "json cases")
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise ValueError("Raw JSON curation must be an object, list, or {'cases': ...}")

    output: dict[str, JsonObject] = {}
    for item in items:
        rich_case = _as_object(item, "json case")
        case_id = _required_str(rich_case.get("case_id"), "json case.case_id")
        if case_id in output:
            raise ValueError(f"Duplicate rich curation case {case_id!r}")
        output[case_id] = rich_case
    return output


def _build_provenance(
    rich_case: Mapping[str, Any],
    provenance_overlay: Mapping[str, Any],
) -> JsonObject:
    provenance: JsonObject = {
        "status": "github_issue_maintainer_resolution",
        "source_url": _optional_str(rich_case.get("source_url")),
        "verbatim_diagnosis_path": "hidden_oracle/provenance.md",
        "note": (
            "Generated from rich curation metadata. Grader-facing requirements came "
            "from an explicit overlay, not from free-form rubric text."
        ),
    }
    case_id = _optional_str(rich_case.get("case_id"))
    if case_id:
        provenance["rich_case_id"] = case_id

    for key in _PROVENANCE_KEYS:
        value = rich_case.get(key)
        if value not in (None, "", [], {}):
            provenance[key] = value

    authorities = _extract_authorities(rich_case)
    if authorities:
        provenance["authorities"] = authorities

    for key, value in provenance_overlay.items():
        provenance[str(key)] = value
    return provenance


def _extract_authorities(rich_case: Mapping[str, Any]) -> list[JsonObject]:
    raw_entries = _required_list(rich_case.get("verbatim_diagnoses", []), "verbatim_diagnoses")
    seen: set[tuple[str, str, str]] = set()
    authorities: list[JsonObject] = []
    for raw_entry in raw_entries:
        entry = _as_object(raw_entry, "verbatim diagnosis")
        author = _optional_str(entry.get("author"))
        name = _optional_str(entry.get("author_name"))
        role = _optional_str(entry.get("role"))
        fingerprint = (author or "", name or "", role or "")
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        authority: JsonObject = {}
        if author:
            authority["github"] = author
        if name:
            authority["name"] = name
        if role:
            authority["role"] = role
        if authority:
            authorities.append(authority)
    return authorities


def _render_known_metadata(rich_case: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in _PROVENANCE_KEYS:
        value = rich_case.get(key)
        if value in (None, "", [], {}):
            continue
        rendered = json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value)
        lines.append(f"- `{key}`: {rendered}")

    extra_text_keys = (
        "actual_offender",
        "expected_agent_behavior",
        "adversarial_property",
        "notes",
        "two_cherry_accounts_note",
        "open_question_in_thread",
        "verification_note",
    )
    for key in extra_text_keys:
        value = rich_case.get(key)
        if value not in (None, "", [], {}):
            lines.append(f"- `{key}`: {value}")
    return lines


def _render_artifact_references(rich_case: Mapping[str, Any]) -> list[str]:
    artifacts = _required_list(rich_case.get("input_artifacts", []), "input_artifacts")
    lines: list[str] = []
    for artifact in artifacts:
        entry = _as_object(artifact, "input artifact")
        filename = _optional_str(entry.get("filename")) or "unnamed artifact"
        url = _optional_str(entry.get("url"))
        if url:
            lines.append(f"- `{filename}`: {url}")
        else:
            lines.append(f"- `{filename}`")
    return lines


def _quote_block(text: str) -> list[str]:
    lines = text.splitlines() or [text]
    return [f"> {line}" if line else ">" for line in lines]


def _append_optional_bullet(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"- {label}: {value}")


def _as_object(value: Any, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _required_object(value: Any, label: str) -> JsonObject:
    return _as_object(value, label)


def _optional_object(value: Any, label: str) -> JsonObject:
    if value is None:
        return {}
    return _as_object(value, label)


def _required_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _required_string_list(value: Any, label: str) -> list[str]:
    values = _required_list(value, label)
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"{label} must contain only strings")
    return list(values)


def _required_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


if __name__ == "__main__":
    main()
