# eda-parse development log

A short chronological record of implementation decisions that are useful to future contributors.

## 2026-05-11 kickoff

Goal: scaffold the repo and ship the weekend-1 surface:

- Liberty parser
- LEF parser
- Shared `ParsedDocument` and `Chunk` interface
- LangChain loaders
- Real fixture tests
- README and CI

## Fixture policy

The original validation plan included proprietary academic/CMC PDK files. Those files are useful for private validation but cannot be committed. Public tests use redistributable open fixtures instead:

- SKY130 via public OpenSTA/OpenROAD fixture paths
- ASAP7 small Liberty files via OpenSTA fixtures

Private PDK validation should stay out of the repo. If proprietary kits are used, only summary statistics such as cell counts, macro counts, parser timings, and pass/fail status should be recorded.

## Scaffolding choices

- `src/` layout to avoid accidental local imports.
- `hatchling` build backend.
- Python 3.10+.
- Hard dependency: `pydantic`.
- Optional LangChain dependency: `langchain-core`.
- Hand-rolled recursive-descent parsers for Liberty and LEF, because both formats are bracket/block data formats rather than general programming languages.
- `ruff`, `mypy --strict`, and `pytest` in CI.

## Document model

`ParsedDocument` is the top-level parser return type. It stores a human-readable summary, format metadata, semantic chunks, and the raw AST. `Chunk` is the retrieval unit. The LangChain conversion keeps document metadata under `doc_*` keys so chunk-level metadata can retain native names without collisions.

## Current parser status

- Liberty parses real ASAP7 and SKY130 Liberty fixtures.
- LEF parses real SKY130 tech and merged LEF fixtures.
- SDC parses the `gcd_sky130hd.sdc` fixture (1 clock + 1 input_delay + 1 output_delay + 1 input_transition + 3 `set` assignments).
- SPEF fixture is present for future work; parser not implemented yet.

## v0.2.0 (2026-05-11)

Added:

- **SDC parser.** Hand-rolled TCL-ish tokenizer + statement dispatcher. Tracks `set` assignments and resolves `$var` substitutions inline at parse time so downstream metadata carries final numeric values where possible (`create_clock -period $period` becomes `period: 5.0` when `set period 5` appeared earlier). Recognizes `create_clock`, `create_generated_clock`, `set_input_delay`, `set_output_delay`, `set_input_transition`, `set_load`, `set_false_path`, `set_multicycle_path`, `set_clock_groups`. One chunk per constraint; per-kind counts surfaced as document-level metadata.
- **SDCLoader.** Same shape as `LibertyLoader` / `LEFLoader`.
- **`examples/demo_corpus_qa.py`.** Concrete-question script over the real SKY130 Liberty + LEF + SDC trio. Answers five questions (clocks, cells, macros, PVT corner, cross-document sanity check) using only the structured metadata the parsers emit — no embedding model, no LLM. An optional `--with-rag` flag layers a sentence-transformer + FAISS retriever on top for genuinely open-ended queries.

Notes:

- TCL bracket expressions (`[expr ...]`, `[get_ports clk]`) are captured as text, not evaluated. Documented as a known limitation.
- Brace-list contents are joined with single spaces (we tokenize first, so original whitespace inside `{...}` is lost). Cosmetic; downstream consumers can re-normalize.
- The `gcd` SDC names design-level ports, not library cells — the cross-doc Q5 in the demo correctly reports zero matches and explains why. Future demos with synthesized netlists will give richer cross-doc joins.

## Agent-benchmark direction (2026-05-11)

Added `benchmarks/timing_diagnosis/` as the first harness for the agent-workflow side of the project. This is deliberately separate from the parser acceptance testbench:

- Parser testbench asks: "Did `eda-parse` extract stable facts from real public artifacts?"
- Timing-diagnosis harness asks: "Can an agent inspect timing artifacts, diagnose a failure, cite evidence, and propose a concrete next action?"

The harness uses a visible/hidden split: agents see `prompt.md` and `input/`; graders see `hidden_oracle/golden.json`. The same schema can grade first-principles seed tasks, OpenSTA/PrimeTime-generated physics tasks, and sealed authority cases written by a human or pulled from trusted public issue resolutions.

Current seed tasks are marked `physics_first_principles` / `seed_fixture_not_external_sta`. They are for validating the harness contract only. The high-signal next step is to add one sealed `external_authority` timing-failure case and one regenerated `external_tool` OpenSTA/PrimeTime case.

## Agent runner + first authority case (2026-05-11, later)

The "subject side" of the bench landed:

- **`benchmarks/timing_diagnosis/agent.py`** — Claude-callable agent runner with sandboxed tool surface (`read_file`, `list_dir`, `grep`, `parse_liberty`, `parse_lef`, `parse_sdc`, `final_answer`). All file paths sandbox to `task_dir/input/` so the agent can never reach `hidden_oracle/`. Two `ModelClient` implementations: `AnthropicClient` (real SDK with adaptive thinking + effort + prompt caching on system+tools prefix) and `MockClient` (replays scripted JSON of model turns — used by every test in CI, zero API calls). The `final_answer` tool's `input_schema` exactly matches the grader's contract: failing_stage / violation_type / root_cause / clock / three numerics / evidence[] / next_action / confidence / additional_fields (which the runner flattens onto the top level before grading).
- **`tests/test_timing_diagnosis_agent.py`** — 14 tests covering sandbox safety, tool round-trips, end-to-end mock-driven loop scoring PASS at 100% on `physics_001`, additional_fields flattening, max_iters exhaustion stub, error recovery on bad tool args, transcript JSONL.
- **`benchmarks/timing_diagnosis/tasks/authority_001_ol_1371_hold_repair_setup_conflict/`** — first real external-authority case. Sourced from OpenLane GitHub issue #1371, where James Cherry (jjcherry56, OpenSTA author), Anton Blanchard (antonblanchard, IBM/Linux kernel), and Mohamed Gaber (donn, OpenLane lead) diagnosed a hold-repair-blocked-by-setup-violations failure. Real artifacts (1.2 MB after stripping the synthesized netlist): the failing `16-resizer.log` with `RSZ-0064 Unable to repair all hold checks within margin`, the OpenLane scripts, the SDC files, the env (with `GLB_RESIZER_ALLOW_SETUP_VIOS=0`). The grader-shaped `golden.json` lives beside `provenance.md` which carries the verbatim quotes + fix commit (`openroad 79313e90d`) + the audit trail. Validates structurally and grades PASS at 100% on a mock answer.

Schema-mismatch lesson surfaced this session: research-Claude's first curation pass produced rich-format goldens (`verbatim_diagnoses[]`, `fix_commit`, `grading_rubric`) that the grader doesn't read. Resolution: keep the grader contract minimal and uniform; rich content goes in `provenance.md` beside `golden.json`. The split is now documented in `docs/golden-schema.md` so future curation agents produce grader-compatible output directly.

Codex's harness test got patched from "exactly the 3 physics seeds" to "physics seeds present and every loaded task validates" so the corpus can grow without breaking the test.

Repo state: 42/42 pytest pass, ruff clean, mypy `--strict` clean across 9 source files. Working tree has the agent + first authority case + AGENTS.md + docs uncommitted; coordinated commits coming.

## Operating manual + roadmap (2026-05-11, later still)

Added the documents that let other agents pick up work without re-deriving the principles:

- **`AGENTS.md`** at repo root — the operating manual. Quick orientation, engineering invariants, multi-agent collaboration rules, the chamber-check rule, the two-sided artifact pattern, authority-case curation playbook, attribution obligations.
- **`docs/PLAN.md`** — current state, the 16 verified candidate authority cases queued for wiring, ranked open work (real Anthropic API call against authority_001 is the highest-signal next move), things-to-not-do.
- **`docs/bench-design.md`** — design philosophy of the bench: two parts built together, two-tier oracle (physics + authority), chamber-check principle, visible/hidden split, schema-as-API, why TerminalBench shape, what the bench is *not*, honest open gaps.
- **`docs/golden-schema.md`** — exact spec for `hidden_oracle/golden.json` so future curation agents (especially research-Claude on subsequent passes) produce grader-compatible output directly. Worked example uses the OL-1371 case.
- **`docs/why.md`** — updated with SemiAnalysis 2026 framing: 50%/year complexity vs 20%/year productivity gap; verification = 70% of effort; Big Three (Synopsys/Cadence/Siemens) + NVIDIA all have private agentic flows; the wedge is openness + observability + measurement, not building a better closed agent.

These are durable; future agents in cold-context sessions can pick up where this one left off without losing the principles.

## Curation converter (2026-05-12)

Added `tools/convert_curation_to_golden.py` so the authority backlog no longer depends on
manual copy/paste between research-Claude's rich curation dumps and the bench oracle shape.

The converter accepts:

- the rich markdown dump format with headings like
  `tasks/OL-1371/hidden_oracle/golden.json`
- or raw JSON containing the same rich case payloads
- a separate overlay keyed by `case_id` that supplies the grader contract fields the rich
  dump intentionally does **not** specify (`required_exact`, `required_numeric`,
  `required_evidence`, `required_next_action_terms`, plus the final bench `task_id`)

That split is intentional. Verbatim maintainer quotes, fix metadata, and attribution flow
into `provenance.md`; benchmark truth still comes from an explicit hand-reviewed overlay
rather than heuristically "understanding" rubric prose. Focused tests now cover extraction,
golden assembly, provenance rendering, and on-disk conversion.

## Authority cases 002 and 003 (2026-05-12)

Wired the two adversarial authority cases called out in the bench design:

- `authority_002_ol_958_report_clock_skew_feedback_loop`
- `authority_003_or_4833_report_metrics_bottleneck`

Both were re-verified against the live GitHub issue threads before wiring. `OL-958`
preserves Cherry's explicit rejection of the misleading clockless-design comment and the
`OpenROAD e3315ba41` fix note. `OR-4833` preserves Eder Matheus Monteiro's rerun showing the
issue title misattributes the stall to antenna repair when the real two-hour bottleneck is
`report_metrics`.

Input trimming mattered:

- `OL-958` had multi-megabyte attached packages; the task keeps the small standalone Tcl
  testcase, the load-bearing `sta.tcl` excerpt, and a public-thread excerpt.
- `OR-4833` pointed to a 473 MB BoomTile tarball; the task keeps only the small GRT log tail,
  the post-route Tcl tail, and a public-thread excerpt.

The grader-facing goldens/provenance for both tasks are generated from the preserved rich
curation payload through `tools/convert_curation_to_golden.py`, using the checked-in overlay
file `benchmarks/timing_diagnosis/curation_overlays/authority_002_003.json`.

## First real authority-tier runs + grader calibration (2026-05-12)

Ran Claude Opus 4.7 with high effort against `authority_001`, `authority_002`, and
`authority_003`. The first pass exposed benchmark calibration bugs rather than subject-agent
diagnosis failures:

- evidence tokens like `RSZ-0064` were unsatisfiable when the answer schema asked for
  `input/path:line` references rather than pasted source text
- legitimate `root_cause` paraphrases failed strict whole-string matching
- `read_file` returned raw text without line numbers, making exact evidence citations easy to
  drift by one or two lines

The instrument was tightened accordingly:

- evidence grading now dereferences visible `input/...:line` citations, with a small local context
  window for pre-line-number runs
- authority-tier `root_cause` values keep exact matching first, then accept bounded token-overlap
  paraphrases
- `read_file` returns 1-based line-numbered content

After those changes, all three real answers regrade PASS at 100%. The preserved run artifacts
live under `evidence/v0_first_real_runs/`; they include the final structured answers and the
tool-call transcripts, plus the useful retry wrapper log for `authority_001`.
