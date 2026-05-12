# Golden answer schema — `hidden_oracle/golden.json`

This is the exact contract the grader in `benchmarks/timing_diagnosis/harness.py` walks. **Any new task's `golden.json` must match this shape, regardless of how the gold answer was sourced (physics derivation, OpenSTA run, sealed maintainer comment, etc.).**

The format below was originally established by Codex's harness and aligns with METRICS2.1 conventions (Jung, Kahng, Kim, Varadarajan, ICCAD 2021). Don't invent richer formats here — put rich provenance in `hidden_oracle/provenance.md` *beside* `golden.json`. The grader reads `golden.json`; auditors read `provenance.md`.

## Required top-level fields

```json
{
  "task_id": "<string, must match task.json>",
  "oracle_type": "physics_first_principles | external_tool | external_authority",
  "required_exact": { ... },
  "required_numeric": { ... },
  "required_evidence": [ "..." ],
  "required_next_action_terms": [ "..." ]
}
```

Optional but recommended:

```json
{
  "provenance": { ... }
}
```

The `provenance` block is not graded but is a useful place to drop a one-line pointer to `provenance.md`, the source URL, the fix commit, and the named authorities. Carry the rich detail in the markdown file.

## Field-by-field reference

### `task_id` (string, required)

Must equal `task.json`'s `task_id`. The harness checks this match in `validate_task()`.

### `oracle_type` (string, required)

One of:

- `physics_first_principles` — hand-constructed seed fixture with deterministic arithmetic. Use only for harness-development cases under `tasks/physics_*/`. Mark `provenance.status` as `seed_fixture_not_external_sta`.
- `external_tool` — golden derived from a real EDA tool (OpenSTA, PrimeTime, Genus, Innovus, etc.). Mark `provenance.status` with the tool name and command.
- `external_authority` — golden sealed by a named human authority (GitHub issue maintainer comment, paper, textbook). Mark `provenance.status` as `github_issue_maintainer_resolution` (or similar) and link the source.

Must equal `task.json`'s `oracle_type`. Harness checks this too.

### `required_exact` (object, required, may be empty)

Map of `field_name -> expected_value` checked with case-insensitive whitespace-normalised string equality.
For `root_cause` on `external_authority` tasks, the grader also accepts close
snake_case paraphrases with substantial token overlap against one listed
answer. This keeps authority cases from failing solely because a model wrote
`report_metrics_dominates_grt_runtime` instead of
`post_global_route_report_metrics_dominates_runtime`. Other exact fields stay
strict.

The `expected_value` may be:

- A single string (`"setup"`) — agent must match exactly.
- A list of strings (`["clock_period_too_short", "overconstrained_clock"]`) — agent matches if its answer equals **any one** of them. Use this for any field where multiple correct phrasings are acceptable (`root_cause` is the usual case).

```json
"required_exact": {
  "failing_stage": ["static_timing", "place_and_route", "post_route_timing_repair"],
  "violation_type": "hold",
  "root_cause": [
    "hold_repair_blocked_by_setup_violations",
    "setup_violations_block_hold_repair"
  ]
}
```

Standard fields the agent's `final_answer` tool emits:

| Field | Meaning |
|---|---|
| `failing_stage` | `static_timing`, `logic_synthesis`, `place_and_route`, `post_route_timing_repair`, `drc`, `lvs`, `constraint_check`, etc. Snake_case. |
| `violation_type` | `setup`, `hold`, `drc`, `lvs`, `unconstrained_paths`, `constraint_coverage`, `other`. |
| `root_cause` | Short snake_case identifier. Be specific (`clock_period_too_short`, not `bad_timing`). |
| `clock` | Name of the affected clock if applicable. |

You can require additional task-specific fields here (e.g. `unconstrained_input_count` when relevant). The agent's `additional_fields` map gets flattened onto the top level before grading, so any name works.

### `required_numeric` (object, required, may be empty)

Map of `field_name -> {value, tolerance}`. Compared with `abs(observed - expected) <= tolerance`.

```json
"required_numeric": {
  "declared_period_ns": {"value": 1.0, "tolerance": 0.001},
  "worst_slack_ns": {"value": -0.42, "tolerance": 0.001},
  "minimum_passing_period_ns": {"value": 1.42, "tolerance": 0.01}
}
```

Set tolerances tightly enough that wrong arithmetic fails, loosely enough that legitimate floating-point noise doesn't. For numbers derived from a tool report (slack to 0.01 ns), `0.001` to `0.01` is a sensible band.

When the case has no required numerics (common for authority cases that test reasoning, not arithmetic), pass `{}`.

### `required_evidence` (list of strings, required, may be empty)

The grader checks each token is a **case-insensitive substring** of either:

- the agent's joined `evidence[]` array, or
- the contents of the task-visible `input/...:line` references cited there,
  including a small nearby-line context window.

Use this to require that the agent cite specific source files or tool error
codes by name. The grader only dereferences files under the task's visible
`input/` directory; hidden oracles are never searched.

```json
"required_evidence": [
  "16-resizer.log",
  "RSZ-0064"
]
```

The agent emits something like:
```json
"evidence": [
  "input/16-resizer.log:824",
  "input/reproducer/run.sh:35 GLB_RESIZER_ALLOW_SETUP_VIOS=0"
]
```

`16-resizer.log` appears in the evidence reference, and `RSZ-0064` appears on
the cited line or its small nearby context in the input artifact, so both
required tokens pass.

Don't over-require. Two to four tokens is usually right. Each token represents *one fact the agent must have looked at*.

### `required_next_action_terms` (list of strings, required, may be empty)

Same substring-presence check, applied to the `next_action` string. Use this to require the agent name a specific environment variable, command, file path, or numeric target in its proposed fix.

```json
"required_next_action_terms": ["GLB_RESIZER_ALLOW_SETUP_VIOS"]
```

Or:

```json
"required_next_action_terms": ["relax", "period"]
```

Choose terms an *unambiguously correct* answer must use. Don't pick terms that a wrong answer could also stumble into.

### `provenance` (object, optional, ungraded)

A breadcrumb trail. Suggested shape:

```json
"provenance": {
  "status": "github_issue_maintainer_resolution",
  "source_url": "https://github.com/The-OpenROAD-Project/OpenLane/issues/1371",
  "fix_commit": "openroad 79313e90d",
  "fix_file_path": "src/rsz/src/RepairHold.cc",
  "user_workaround_env_var": "GLB_RESIZER_ALLOW_SETUP_VIOS",
  "authorities": [
    {"github": "jjcherry56", "name": "James Cherry", "role": "OpenSTA author / Parallax Software"}
  ],
  "verbatim_diagnosis_path": "hidden_oracle/provenance.md",
  "note": "Maintainer-sealed answer key. Verbatim quotes live in provenance.md."
}
```

The graders ignore everything in `provenance`. Its purpose is to make the case auditable when someone asks "why is this the right answer?"

## Worked example (`authority_001_ol_1371_hold_repair_setup_conflict`)

```json
{
  "task_id": "authority_001_ol_1371_hold_repair_setup_conflict",
  "oracle_type": "external_authority",
  "provenance": {
    "status": "github_issue_maintainer_resolution",
    "source_url": "https://github.com/The-OpenROAD-Project/OpenLane/issues/1371",
    "fix_commit": "openroad 79313e90d",
    "user_workaround_env_var": "GLB_RESIZER_ALLOW_SETUP_VIOS",
    "verbatim_diagnosis_path": "hidden_oracle/provenance.md"
  },
  "required_exact": {
    "failing_stage": ["static_timing", "place_and_route", "post_route_timing_repair", "hold_repair"],
    "violation_type": "hold",
    "root_cause": [
      "hold_repair_blocked_by_setup_violations",
      "setup_violations_block_hold_repair",
      "hold_fixup_disabled_when_setup_violates",
      "allow_setup_violations_disabled"
    ]
  },
  "required_numeric": {},
  "required_evidence": ["16-resizer.log", "RSZ-0064"],
  "required_next_action_terms": ["GLB_RESIZER_ALLOW_SETUP_VIOS"]
}
```

Sits beside `provenance.md` which carries the verbatim Cherry / Blanchard / Donn quotes, the source URL, the fix commit, the audit trail. Together they let the grader work and let an auditor verify nothing was made up.

## Common mistakes the schema is designed to catch

- **Inventing "rubric" or "grading" fields the grader doesn't read.** If a field doesn't appear in this spec, the grader ignores it. Put rich rubrics in `provenance.md`, not `golden.json`.
- **Single-string `root_cause` when multiple phrasings are valid.** Use a list. Grader matches any one.
- **Tolerances too tight on numerics derived from coarse reports.** A timing report quoted to 0.01 ns shouldn't have a 0.0001 ns tolerance — false fails on rounding.
- **Required evidence tokens that are too generic.** "design.v" matches every Verilog file; prefer "RSZ-0064" or "constraints.sdc".
- **`task_id` mismatch with `task.json`.** The harness validation step fails fast on this. Always copy from `task.json`.

## When in doubt

Look at the worked examples in `benchmarks/timing_diagnosis/tasks/`. The four currently-shipped cases (three physics seeds + the OL-1371 authority case) cover the field shapes you'll need to reuse.

If something legitimately doesn't fit this schema, raise it before extending the schema — the grader is the contract, and changing it touches every existing task.
