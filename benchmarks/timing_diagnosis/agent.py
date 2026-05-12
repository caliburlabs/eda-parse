"""Agent runner for the timing-diagnosis benchmark.

This module is the **subject side** of the bench: the harness that drives a
language model (Claude, via the Anthropic SDK) through a fixed tool surface
against a frozen task fixture, until the model emits a structured diagnosis
that the grader in :mod:`benchmarks.timing_diagnosis.harness` can score.

Two design constraints shape this file:

1. **The agent must not be able to read the hidden oracle.** Every
   file-system tool resolves paths through :func:`_safe_input_path`, which
   sandboxes access to ``task_dir/input``. The agent literally cannot
   address anything else.

2. **The bench must be runnable without API credentials.** Tests and CI
   should never hit the network. The :class:`ModelClient` protocol lets a
   :class:`MockClient` replay a scripted set of model turns deterministically,
   keeping the rest of the loop (tool execution, grader contract, transcript
   logging) on the real code path.

The real :class:`AnthropicClient` configures adaptive thinking, the
``effort`` parameter, and prompt caching on the stable ``system`` + ``tools``
prefix so repeated runs against the same fixture share most input tokens.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from eda_parse.parsers import lef, liberty, sdc

# Lazy SDK import — agent.py loads without anthropic installed, so the
# scripted mock path works in CI without an extra dependency.
try:  # pragma: no cover - import-time path
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment,unused-ignore]


# ----------------------------------------------------------------------
# Path sandbox
# ----------------------------------------------------------------------


class PathSandboxError(ValueError):
    """Raised when a tool tries to access a path outside ``input/``."""


def _safe_input_path(task_dir: Path, requested: str) -> Path:
    """Resolve ``requested`` relative to ``task_dir/input`` and reject any
    path that escapes that root via traversal, absolute paths, or symlinks.

    The agent never sees ``task_dir`` directly — it sees ``input/...`` paths
    and writes them in that form. Both ``input/constraints.sdc`` and bare
    ``constraints.sdc`` resolve to the same place. Absolute paths and paths
    that traverse out of ``input/`` are rejected explicitly so the agent
    gets a clear sandbox-error tool result, not a quiet "file not found".
    """
    root = (task_dir / "input").resolve()
    cleaned = requested
    if cleaned.startswith("input/") or cleaned.startswith("input\\"):
        cleaned = cleaned.split("input", 1)[1].lstrip("/").lstrip("\\")
    # After stripping the optional 'input/' prefix, the path must be
    # relative — anything still starting with a slash is an absolute path
    # outside the sandbox.
    if cleaned.startswith("/") or cleaned.startswith("\\"):
        raise PathSandboxError(
            f"absolute path {requested!r} is not allowed; "
            "paths must be relative to input/"
        )
    candidate = (root / cleaned).resolve()
    if candidate != root and root not in candidate.parents:
        raise PathSandboxError(
            f"path {requested!r} resolves outside the sandboxed input/ directory"
        )
    return candidate


# ----------------------------------------------------------------------
# Tool handlers
# ----------------------------------------------------------------------

# Cap on how much text any single tool returns. Keeps the transcript bounded
# even when the agent grabs a 30K-line library file.
_MAX_TOOL_OUTPUT_CHARS = 60_000


def _truncate(text: str) -> str:
    if len(text) <= _MAX_TOOL_OUTPUT_CHARS:
        return text
    return (
        text[:_MAX_TOOL_OUTPUT_CHARS]
        + f"\n\n[... truncated; full file is {len(text)} chars total ...]"
    )


def _with_line_numbers(text: str) -> str:
    return "\n".join(f"{line_no}: {line}" for line_no, line in enumerate(text.splitlines(), 1))


def _tool_read_file(task_dir: Path, *, path: str) -> str:
    p = _safe_input_path(task_dir, path)
    if not p.exists():
        return f"ERROR: {path!r} not found"
    if not p.is_file():
        return f"ERROR: {path!r} is not a regular file"
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
            return _truncate(_with_line_numbers(fh.read()))
    return _truncate(_with_line_numbers(p.read_text(encoding="utf-8", errors="replace")))


def _tool_list_dir(task_dir: Path, *, path: str = "") -> str:
    root = (task_dir / "input").resolve()
    target = _safe_input_path(task_dir, path) if path else root
    if not target.exists():
        return f"ERROR: {path or 'input'} not found"
    if not target.is_dir():
        return f"ERROR: {path!r} is not a directory"
    lines: list[str] = []
    for item in sorted(target.iterdir()):
        rel = item.relative_to(root)
        if item.is_dir():
            lines.append(f"input/{rel}/")
        else:
            lines.append(f"input/{rel}  ({item.stat().st_size} bytes)")
    return "\n".join(lines) if lines else "(empty)"


def _tool_grep(task_dir: Path, *, pattern: str, path: str) -> str:
    p = _safe_input_path(task_dir, path)
    if not p.exists():
        return f"ERROR: {path!r} not found"
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"ERROR: invalid regex {pattern!r}: {exc}"
    root = (task_dir / "input").resolve()
    files = [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.is_file())
    matches: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                rel = f.relative_to(root)
                matches.append(f"input/{rel}:{i}: {line}")
                if len(matches) >= 200:
                    matches.append("[... more matches truncated ...]")
                    return "\n".join(matches)
    return "\n".join(matches) if matches else f"(no matches for {pattern!r} in {path})"


def _tool_parse_liberty(task_dir: Path, *, path: str) -> str:
    p = _safe_input_path(task_dir, path)
    doc = liberty.parse(p)
    summary = {
        "library": doc.metadata.get("library"),
        "technology": doc.metadata.get("technology"),
        "delay_model": doc.metadata.get("delay_model"),
        "cell_count": doc.metadata.get("cell_count"),
        "total_pin_count": doc.metadata.get("total_pin_count"),
        "operating_conditions": doc.metadata.get("operating_conditions"),
        "time_unit": doc.metadata.get("time_unit"),
        "voltage_unit": doc.metadata.get("voltage_unit"),
        "nom_voltage": doc.metadata.get("nom_voltage"),
        "nom_temperature": doc.metadata.get("nom_temperature"),
        "first_cells": [c.metadata.get("cell_name") for c in doc.chunks[:15]],
    }
    return json.dumps(summary, indent=2)


def _tool_parse_lef(task_dir: Path, *, path: str) -> str:
    p = _safe_input_path(task_dir, path)
    doc = lef.parse(p)
    layer_names = doc.metadata.get("layer_names") or []
    summary = {
        "lef_kind": doc.metadata.get("lef_kind"),
        "version": doc.metadata.get("version"),
        "manufacturing_grid": doc.metadata.get("manufacturing_grid"),
        "units": doc.metadata.get("units"),
        "layer_count": doc.metadata.get("layer_count"),
        "site_count": doc.metadata.get("site_count"),
        "via_count": doc.metadata.get("via_count"),
        "viarule_count": doc.metadata.get("viarule_count"),
        "macro_count": doc.metadata.get("macro_count"),
        "first_layers": list(layer_names)[:15],
        "first_macros": [c.metadata.get("macro_name") for c in doc.chunks[:15]],
    }
    return json.dumps(summary, indent=2)


def _tool_parse_sdc(task_dir: Path, *, path: str) -> str:
    p = _safe_input_path(task_dir, path)
    doc = sdc.parse(p)
    summary = {
        "design": doc.metadata.get("design"),
        "variables": doc.metadata.get("variables"),
        "clock_count": doc.metadata.get("clock_count"),
        "generated_clock_count": doc.metadata.get("generated_clock_count"),
        "input_delay_count": doc.metadata.get("input_delay_count"),
        "output_delay_count": doc.metadata.get("output_delay_count"),
        "input_transition_count": doc.metadata.get("input_transition_count"),
        "load_count": doc.metadata.get("load_count"),
        "false_path_count": doc.metadata.get("false_path_count"),
        "multicycle_path_count": doc.metadata.get("multicycle_path_count"),
        "clock_groups_count": doc.metadata.get("clock_groups_count"),
        "constraints": [
            {"kind": c.kind, "metadata": c.metadata} for c in doc.chunks
        ],
    }
    return json.dumps(summary, indent=2)


_TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "read_file": _tool_read_file,
    "list_dir": _tool_list_dir,
    "grep": _tool_grep,
    "parse_liberty": _tool_parse_liberty,
    "parse_lef": _tool_parse_lef,
    "parse_sdc": _tool_parse_sdc,
}


# ----------------------------------------------------------------------
# Tool schemas sent to the model
# ----------------------------------------------------------------------

# Schema kept in sync with the grader's expected answer shape — see
# benchmarks/timing_diagnosis/README.md and the goldens under tasks/.
_FINAL_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "failing_stage": {
            "type": "string",
            "description": (
                "Which stage of the flow failed: 'static_timing', 'logic_synthesis', "
                "'place_and_route', 'drc', 'lvs', or 'other'. Use snake_case."
            ),
        },
        "violation_type": {
            "type": "string",
            "description": (
                "Nature of the violation: 'setup', 'hold', 'drc', 'lvs', "
                "'unconstrained_paths', or 'other'."
            ),
        },
        "root_cause": {
            "type": "string",
            "description": (
                "Short snake_case identifier for the root cause, e.g. "
                "'clock_period_too_short', 'missing_input_delay', "
                "'overconstrained_clock', 'unconstrained_paths'."
            ),
        },
        "clock": {
            "type": "string",
            "description": "Name of the affected clock, if applicable.",
        },
        "declared_period_ns": {
            "type": "number",
            "description": "Clock period declared in the SDC, in nanoseconds.",
        },
        "worst_slack_ns": {
            "type": "number",
            "description": (
                "Worst slack reported (negative = violating), in nanoseconds."
            ),
        },
        "minimum_passing_period_ns": {
            "type": "number",
            "description": (
                "Smallest clock period that would close the worst violating "
                "path, derived from the report arithmetic."
            ),
        },
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "List of 'input/path:line' references that support the diagnosis. "
                "Use the same path strings the read_file / grep tools accept."
            ),
        },
        "next_action": {
            "type": "string",
            "description": (
                "One concrete next engineering change to address the failure, "
                "phrased in plain English."
            ),
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Self-reported confidence in the diagnosis.",
        },
        "additional_fields": {
            "type": "object",
            "description": (
                "Task-specific extra fields when the prompt asks for them "
                "(e.g. unconstrained_input_count). These are flattened to the "
                "top level of the answer JSON before grading."
            ),
            "additionalProperties": True,
        },
    },
    "required": [
        "failing_stage",
        "violation_type",
        "root_cause",
        "evidence",
        "next_action",
    ],
}


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": (
            "Read a file from the task's input/ directory and return its text "
            "contents with 1-based line numbers. Paths must be inside input/ — "
            "anything else is rejected. "
            "Both 'constraints.sdc' and 'input/constraints.sdc' work. Gzipped "
            "files (.gz) are decompressed transparently. Output truncated at "
            f"~{_MAX_TOOL_OUTPUT_CHARS} characters."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Path under input/, e.g. 'constraints.sdc' or "
                        "'reports/timing_report.rpt'."
                    ),
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": (
            "List files and directories under input/. Pass an empty path to "
            "list the input/ root."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path under input/. Empty for root.",
                }
            },
        },
    },
    {
        "name": "grep",
        "description": (
            "Search for a Python regex pattern in a file or directory under "
            "input/. Returns matching lines as 'input/path:lineno: content'. "
            "Capped at 200 matches per call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python regex."},
                "path": {
                    "type": "string",
                    "description": "File or directory path under input/.",
                },
            },
            "required": ["pattern", "path"],
        },
    },
    {
        "name": "parse_liberty",
        "description": (
            "Parse a Liberty (.lib or .lib.gz) standard-cell library with "
            "eda-parse. Returns the library name, technology, PVT operating "
            "conditions, units, cell and pin counts, and the first 15 cell "
            "names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "parse_lef",
        "description": (
            "Parse a LEF (.lef or .tlef) library exchange file with eda-parse. "
            "Returns lef_kind (tech/cell/merged), units, layer/site/via/macro "
            "counts, and the first 15 layer and macro names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "parse_sdc",
        "description": (
            "Parse an SDC (Synopsys Design Constraints) file with eda-parse. "
            "Returns tracked variable assignments (with $var references "
            "resolved at parse time), per-constraint-kind counts, and the full "
            "list of constraint chunks: clocks, generated_clocks, input/output "
            "delays, transitions, loads, false paths, multicycle paths, and "
            "clock groups."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "final_answer",
        "description": (
            "Submit the final structured diagnosis. Calling this tool ENDS "
            "the agent loop. Fill in every field you can support with "
            "evidence from the artifacts you read. Numeric fields are scored "
            "with a tolerance; string fields are compared after lowercasing "
            "and whitespace-normalising. If the prompt asks for any "
            "task-specific extra field (e.g. unconstrained_input_count), put "
            "it under additional_fields with the same key."
        ),
        "input_schema": _FINAL_ANSWER_SCHEMA,
    },
]


# ----------------------------------------------------------------------
# System prompt
# ----------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a careful EDA timing-diagnosis agent.

You are given a sealed bundle describing one chip-design run that failed
some part of the flow (synthesis, static timing, place-and-route, DRC, or
similar). Your job is to inspect the artifacts under input/, understand
exactly why the failure happened, and produce a single structured JSON
answer via the `final_answer` tool.

How to work:

1. Start by calling `list_dir` to see what's in input/, and reading
   prompt.md (the user message that follows will quote it).
2. Read the relevant artifacts. Use the parse_* tools when they help:
   parse_liberty for .lib files, parse_lef for .lef/.tlef, parse_sdc for
   constraints. Use read_file for reports and Verilog. Use grep to find
   specific lines (slack numbers, port names, error codes).
3. Cite every load-bearing fact with a concrete `input/path:line` in the
   `evidence` array. Do not invent line numbers — if you didn't grep or
   read the line, don't claim it.
4. Be specific in `root_cause`: prefer `clock_period_too_short` over
   `bad_timing`, `missing_input_delay` over `sdc_problem`.
5. `next_action` should be one concrete change a chip engineer can make
   tomorrow, not generic advice.
6. When the report gives you the arrival and required times, derive
   `worst_slack_ns` and `minimum_passing_period_ns` directly from the
   numbers. Don't guess.
7. When you are confident enough to commit, call `final_answer` exactly
   once. Do not call any other tool after `final_answer`.

You are forbidden from making claims you cannot support from the bytes of
input/. If something is unknown, say so plainly in `root_cause` or
`next_action` — a hedged honest answer scores better than a confident
wrong one.
"""


# ----------------------------------------------------------------------
# Model client abstraction
# ----------------------------------------------------------------------


@dataclass
class ToolCall:
    """One tool call requested by the model."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ModelTurn:
    """One assistant turn from the model, normalised for the loop.

    ``assistant_content`` is the raw Anthropic-shape content blocks (a list
    of dicts) that should be appended verbatim to ``messages`` for the next
    request. Preserving the original blocks (including ``tool_use`` blocks
    with their ``id``s and any ``thinking`` blocks) is what keeps
    ``tool_use_id`` correlation valid and the prompt cache warm.
    """

    text: str
    tool_calls: list[ToolCall]
    assistant_content: list[dict[str, Any]]
    stop_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class ModelClient(Protocol):
    """The minimal interface the agent loop needs from a model."""

    def step(
        self,
        *,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> ModelTurn: ...


# Models that accept output_config.effort + adaptive thinking. Conservative
# — only the models the claude-api skill documents as supporting effort.
_EFFORT_AWARE_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-sonnet-4-6",
)
# Models where adaptive thinking is accepted. Haiku 4.5 silently does not
# support adaptive thinking on the same API surface as Opus/Sonnet.
_THINKING_AWARE_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
)


class AnthropicClient:
    """Real ModelClient backed by the Anthropic Python SDK.

    The system + tools render position is fixed and cacheable across runs;
    only the per-task user message and the growing tool-result transcript
    after it vary. Prompt caching is enabled on the system block, so
    repeated runs against the same task share the system + tools prefix.
    """

    def __init__(
        self,
        model: str,
        *,
        effort: str = "high",
        max_tokens: int = 16_000,
    ) -> None:
        if anthropic is None:  # pragma: no cover - import-time guard
            raise RuntimeError(
                "anthropic SDK not installed. Install with: pip install anthropic"
            )
        self._client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def step(
        self,
        *,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> ModelTurn:
        extra: dict[str, Any] = {}
        if self.model.startswith(_THINKING_AWARE_PREFIXES):
            extra["thinking"] = {"type": "adaptive"}
        if self.model.startswith(_EFFORT_AWARE_PREFIXES):
            extra["output_config"] = {"effort": self.effort}

        create_message = cast(Any, self._client.messages.create)
        response = create_message(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            tools=tools,
            messages=messages,
            **extra,
        )
        return _normalise_response(response.model_dump())


def _normalise_response(payload: dict[str, Any]) -> ModelTurn:
    """Translate an Anthropic-shape ``messages.create`` response into a
    :class:`ModelTurn` the agent loop can use directly."""
    content = payload.get("content") or []
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in content:
        kind = block.get("type")
        if kind == "text":
            text_parts.append(str(block.get("text", "")))
        elif kind == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=str(block.get("id", "")),
                    name=str(block.get("name", "")),
                    input=dict(block.get("input") or {}),
                )
            )
    return ModelTurn(
        text="".join(text_parts),
        tool_calls=tool_calls,
        assistant_content=list(content),
        stop_reason=str(payload.get("stop_reason", "")),
        usage=dict(payload.get("usage") or {}),
    )


@dataclass
class MockClient:
    """Scripted ModelClient for tests and CI.

    The ``script`` is a list of turns, each turn a list of Anthropic-shape
    content blocks. The mock returns successive turns on each ``step`` call.
    Once exhausted, further calls raise — that condition is useful in tests
    that want to assert the loop terminated within the scripted number of
    turns.
    """

    script: list[list[dict[str, Any]]]
    _idx: int = 0

    def step(
        self,
        *,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> ModelTurn:
        if self._idx >= len(self.script):
            raise RuntimeError(
                f"MockClient script exhausted after {self._idx} turns; "
                "loop did not terminate when expected"
            )
        content = self.script[self._idx]
        self._idx += 1
        return _normalise_response({"content": content, "stop_reason": "tool_use"})


# ----------------------------------------------------------------------
# The agent loop
# ----------------------------------------------------------------------


@dataclass
class AgentResult:
    """Outcome of one full agent run."""

    answer: dict[str, Any]
    turns: int
    completed: bool  # True if final_answer was called; False if loop bailed
    reason: str  # human-readable termination reason


def _build_system_blocks() -> list[dict[str, Any]]:
    """System message blocks with a cache breakpoint on the last block.

    The system prompt is the stable prefix shared across every task run;
    pinning a cache_control breakpoint here makes repeated runs cheap.
    """
    return [
        {
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _build_initial_user_message(task_dir: Path) -> str:
    prompt_path = task_dir / "prompt.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"missing prompt.md in {task_dir}")
    prompt_text = prompt_path.read_text(encoding="utf-8")
    inventory = _tool_list_dir(task_dir)
    return (
        "Here is the task prompt and an initial listing of the input/ "
        "directory. Inspect whatever you need via the available tools and "
        "then call `final_answer`.\n\n"
        "# prompt.md\n\n"
        f"{prompt_text}\n\n"
        "# input/ directory listing\n\n"
        f"{inventory}\n"
    )


def _flatten_answer(payload: dict[str, Any]) -> dict[str, Any]:
    """Move any keys under ``additional_fields`` up to the top level.

    The grader expects task-specific extras like ``unconstrained_input_count``
    at the top of the answer JSON; the model puts them under
    ``additional_fields`` so the input_schema can stay finite.
    """
    answer = {k: v for k, v in payload.items() if k != "additional_fields"}
    extras = payload.get("additional_fields") or {}
    if isinstance(extras, dict):
        for k, v in extras.items():
            answer.setdefault(k, v)
    return answer


def run_agent(
    task_dir: str | Path,
    *,
    client: ModelClient,
    max_iters: int = 25,
    transcript_path: str | Path | None = None,
) -> AgentResult:
    """Drive the agent against one task fixture and return its diagnosis.

    The caller chooses the model client — pass :class:`AnthropicClient` for
    a real run, :class:`MockClient` for tests. The grader is not invoked
    here; the returned ``answer`` dict is what the caller hands to
    :func:`benchmarks.timing_diagnosis.harness.grade_payload`.
    """
    task_path = Path(task_dir).resolve()
    if not (task_path / "input").is_dir():
        raise FileNotFoundError(f"missing input/ directory in {task_path}")

    transcript: list[dict[str, Any]] = []

    def record(kind: str, data: dict[str, Any]) -> None:
        entry = {"t": time.time(), "kind": kind, **data}
        transcript.append(entry)

    system = _build_system_blocks()
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [{"type": "text", "text": _build_initial_user_message(task_path)}],
        }
    ]
    record("user", {"text": messages[0]["content"][0]["text"]})

    answer: dict[str, Any] = {}
    completed = False
    reason = "loop reached max_iters without final_answer"

    for iteration in range(1, max_iters + 1):
        turn = client.step(system=system, tools=TOOL_DEFINITIONS, messages=messages)
        record(
            "assistant",
            {
                "iteration": iteration,
                "text": turn.text,
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "input": tc.input}
                    for tc in turn.tool_calls
                ],
                "stop_reason": turn.stop_reason,
                "usage": turn.usage,
            },
        )

        messages.append({"role": "assistant", "content": turn.assistant_content})

        if not turn.tool_calls:
            reason = (
                f"model returned no tool calls at iteration {iteration} "
                f"(stop_reason={turn.stop_reason!r})"
            )
            break

        tool_results: list[dict[str, Any]] = []
        final_payload: dict[str, Any] | None = None

        for call in turn.tool_calls:
            if call.name == "final_answer":
                final_payload = _flatten_answer(call.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": "Answer recorded. Conversation complete.",
                    }
                )
                record(
                    "final_answer",
                    {"iteration": iteration, "answer": final_payload},
                )
                continue

            handler = _TOOL_HANDLERS.get(call.name)
            if handler is None:
                result = f"ERROR: unknown tool {call.name!r}"
                is_error = True
            else:
                try:
                    result = handler(task_path, **call.input)
                    is_error = False
                except PathSandboxError as exc:
                    result = f"ERROR: {exc}"
                    is_error = True
                except TypeError as exc:
                    # Wrong/missing tool inputs surface here — surface them
                    # back to the model so it can retry with the right shape.
                    result = f"ERROR: invalid arguments for {call.name}: {exc}"
                    is_error = True
                except Exception as exc:
                    # Intentional broad catch: tool handler exceptions must
                    # surface to the model as ``is_error`` tool_results so it
                    # can retry, never tear down the loop.
                    result = f"ERROR: {type(exc).__name__}: {exc}"
                    is_error = True

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result,
                    **({"is_error": True} if is_error else {}),
                }
            )
            record(
                "tool_result",
                {
                    "iteration": iteration,
                    "tool": call.name,
                    "tool_use_id": call.id,
                    "is_error": is_error,
                    "content_preview": result[:300],
                },
            )

        messages.append({"role": "user", "content": tool_results})

        if final_payload is not None:
            answer = final_payload
            completed = True
            reason = f"final_answer at iteration {iteration}"
            break

    if transcript_path is not None:
        with Path(transcript_path).open("w", encoding="utf-8") as fh:
            for entry in transcript:
                fh.write(json.dumps(entry) + "\n")

    if not completed and not answer:
        # Emit a stub answer so the grader still produces a (failing) report
        # instead of crashing on missing fields.
        answer = {
            "failing_stage": "unknown",
            "violation_type": "unknown",
            "root_cause": "no_final_answer",
            "evidence": [],
            "next_action": "agent did not commit an answer",
            "confidence": 0.0,
            "agent_error": reason,
        }

    return AgentResult(answer=answer, turns=iteration, completed=completed, reason=reason)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def _load_mock_script(path: Path) -> list[list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("mock script must be a JSON array of turns")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the timing-diagnosis agent against one task fixture and "
            "print the structured answer JSON."
        )
    )
    parser.add_argument("task_dir", type=Path, help="Path to a task directory.")
    parser.add_argument(
        "--model",
        default="claude-opus-4-7",
        help="Anthropic model ID (default: claude-opus-4-7).",
    )
    parser.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
        help=(
            "output_config.effort on models that support it (Opus 4.5+/4.6/4.7, "
            "Sonnet 4.6). Ignored on models without effort support."
        ),
    )
    parser.add_argument(
        "--max-iters",
        type=int,
        default=25,
        help="Maximum agent loop iterations before bailing.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=16_000,
        help="max_tokens for each model call.",
    )
    parser.add_argument(
        "--script",
        type=Path,
        help=(
            "If set, use a MockClient that replays this scripted-turn JSON "
            "instead of calling the Anthropic API. Required for CI tests."
        ),
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        help="If set, write a JSONL transcript of all turns to this path.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="If set, write the answer JSON to this file (in addition to stdout).",
    )
    args = parser.parse_args(argv)

    client: ModelClient
    if args.script is not None:
        client = MockClient(script=_load_mock_script(args.script))
    else:
        client = AnthropicClient(
            model=args.model, effort=args.effort, max_tokens=args.max_tokens
        )

    result = run_agent(
        args.task_dir,
        client=client,
        max_iters=args.max_iters,
        transcript_path=args.transcript,
    )

    output = json.dumps(result.answer, indent=2)
    print(output)
    if args.out is not None:
        args.out.write_text(output + "\n", encoding="utf-8")
    return 0 if result.completed else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
