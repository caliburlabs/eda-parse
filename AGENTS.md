# AGENTS.md — Working in this repo as an agent

This document is the operating manual for any agent (Claude, Codex, research-Claude, ultrareview, future agents not yet imagined) picking up work in `caliburlabs/eda-parse`. Read it before editing.

The repo has **two related artifacts** under one roof, and the rest of this file refers to them:

1. **`eda-parse`** — a Python library that parses EDA file formats (Liberty, LEF, SDC today; DEF/VCD/SPEF planned) into structured, LLM-friendly documents. Lives under `src/eda_parse/`.
2. **`benchmarks/timing_diagnosis/`** — an agent-capability benchmark that uses eda-parse as the agent's observability tool. The bench is what lets us *measure* whether agents using these parsers can do real EDA work; eda-parse is the substrate the agents read through. See `docs/bench-design.md` for the design philosophy.

These two things must be built together — neither makes sense in isolation. (See [Two-sided artifact pattern](#two-sided-artifact-pattern) below.)

---

## Quick orientation

```
src/eda_parse/                # the parser library
  parsers/                    # one file per format: liberty.py, lef.py, sdc.py
  loaders.py                  # LangChain BaseLoader subclasses
  types.py                    # ParsedDocument + Chunk pydantic contract
benchmarks/
  timing_diagnosis/
    harness.py                # Codex's grader: load_task / grade_payload / iter_tasks
    run.py                    # CLI: list / validate / grade
    agent.py                  # Claude's agent runner: ModelClient + tool loop
    tasks/                    # the corpus
      physics_*/              # first-principles seed fixtures
      authority_*/            # external-authority cases (sealed maintainer answers)
    templates/authority_case/ # template for a new authority case
tests/                        # pytest — covers harness + agent + parsers
docs/
  PLAN.md                     # roadmap + current state + open work
  bench-design.md             # bench design philosophy (oracle tiers, schema)
  golden-schema.md            # exact spec for hidden_oracle/golden.json
  why.md                      # market framing + positioning
  formats/{liberty,lef,sdc}.md  # per-format spec pages
  dev-log.md                  # chronological session log
```

Fixtures: `tests/fixtures/` for parser tests (small, redistributable PDK files); `benchmarks/timing_diagnosis/tasks/<id>/input/` for bench tasks (artifacts the agent reads). **Hidden oracles** (`tasks/<id>/hidden_oracle/`) are *never* exposed to the agent.

## Engineering invariants (don't break these)

- **Python 3.10+**, type-hinted, `mypy --strict` clean across `src/eda_parse` and `benchmarks/timing_diagnosis/agent.py`.
- **Ruff** with rules `E F W I UP B SIM RUF`, line length 100. Apply `--fix` for safe rewrites.
- **All tests must pass** (`pytest -q`). The harness CI also runs `python benchmarks/timing_diagnosis/run.py validate` and `python benchmarks/workflow_testbench.py`.
- **No proprietary-PDK fixtures committed.** Ever. SKY130 (Apache 2.0), NanGate FreePDK45, ASAP7 only. Anything from a CMC instance, TSMC, GPDK, AMS, MUMPs, or 3IT JFET stays off the public repo. See `tests/fixtures/README.md` for the fixture license table.
- **Real-fixture validation, no synthetic toys.** Every parser is tested against actual industrial PDK files. Add a parser → add a real fixture. No hand-written 5-line `.lib` dummies.
- **Agent path sandbox**: every file-read tool in `benchmarks/timing_diagnosis/agent.py` resolves through `_safe_input_path()`. The agent literally cannot reach `hidden_oracle/`. If you add a tool that reads files, route through the same helper.

## Multi-agent collaboration

Several agents have been working in this repo simultaneously. To avoid trampling each other:

- **Read before editing.** The harness intercepts `Edit` / `Write` if the file changed since the last `Read`; obey the prompt to re-read.
- **System reminders flag external edits.** Reminders that say "the file was modified by the user or by a linter" are usually Codex (or ruff). Treat them as collaborative changes, not stale state to revert.
- **Stage your own work, not blanket `git add -A`.** Multiple in-flight uncommitted changes from different agents is the default state. Stage by name.
- **Commit in coordinated chunks** when both eda-parse + bench changes belong together. Don't half-commit a state that breaks `pytest`.
- **Don't rewrite each other's prose without good reason.** If `docs/why.md` already exists and another agent wrote it, surface a concrete improvement and ask, don't redraft.

Roles and where each agent typically helps:

| Agent | Best at | Won't / shouldn't do |
|---|---|---|
| **Claude (this assistant)** | Architecture, agent-side code, tool harnesses, integration, prose, chamber-checking | Long mechanical bulk fetches; deep EDA-domain expertise |
| **Codex** | Grader, parsers, harness internals, lint/type cleanup, CI wiring | Open-ended product strategy; the chamber-check role |
| **research-Claude** | Survey-and-curate (GitHub issue digs, fixture provenance), market research, sealed-oracle case construction | Producing grader-compatible JSON without an explicit schema spec — see `docs/golden-schema.md` |
| **ultrareview / general-purpose** | Cross-file consistency checks, reading code at depth, finding contradictions | Editing without explicit instruction |

## Chamber check (the most important rule)

Mani has named this explicitly: when 3+ agents are co-designing a system whose purpose is to *produce truthful output*, agreement among the agents is **not** evidence the output is right. It's just confirmation bias scaled across instances.

When this risk is live (any session that's building bench cases, golden answers, or strategic plans):

- Ask "what external party graded this?" If the answer is "we did," it's chamber.
- Ask "what would falsify this?" If nothing in the system can, it's chamber.
- For "authority oracle" cases: refuse "this looks right to me" from any of us as the basis for a golden answer. Authority must come from one of: (a) reality validating a fix downstream, (b) a public domain expert with a name and a permanent record (GitHub maintainer comment, published paper), (c) an industry-standard tool (OpenSTA, Verilator, DRC checker).
- For planning conversations: if the three-agent agreement is converging fast and feeling good, that's a *warning sign*, not confirmation.

The full memo is in `~/.claude/projects/.../memory/feedback_chamber_check.md` (Claude's auto-memory) — but it lives here in the repo too because future agents may not have memory access.

## Two-sided artifact pattern

Same pattern: build the **measurement** and the **subject** together, not in sequence.

- **Side A — instrument**: the bench (`benchmarks/timing_diagnosis/`). Frozen, public, falsifiable. Measures whether an agent can do EDA.
- **Side B — subject**: the agent system that does real work (`agent.py` today; eventually a richer agent with more tools). The product surface.

Each only makes sense in light of the other. A bench without a subject is academic. A subject without a bench is theater. They co-evolve. Don't sequence "build the substrate, then the bench, then the agent." Build the shortest loop that touches both, and let each iteration of one pull the other forward.

The Flodraulic precedent: there was the engineer-facing CAD-trace tool, the data it indexed, and the verification (Mani manually tracing on Windows). Three things defined each other. Same shape here.

## Authority-oracle case curation

When adding a new authority case under `benchmarks/timing_diagnosis/tasks/authority_<N>_<short>/`:

1. **Sourcing.** Pull from GitHub closed issues on OpenROAD, OpenLane, OpenLane2, OpenSTA, Yosys, or similar OSS EDA projects. Look for: clear repro artifacts attached, **named maintainer comment** with diagnosis + fix commit/PR, evidence the fix actually worked downstream.
2. **Verify in-thread.** The maintainer's diagnosis must appear *verbatim* in the issue thread. No paraphrasing. Use `gh issue view <N> -R <repo> --comments` to confirm.
3. **Download the artifacts** to `input/` — don't link to GitHub URLs, they rot. Strip oversized files (multi-MB synthesized netlists, full PDK libraries) unless they're load-bearing for the diagnosis.
4. **Write the golden** in the format spec'd by `docs/golden-schema.md`. The grader walks `required_exact` / `required_numeric` / `required_evidence` / `required_next_action_terms`, not richer formats.
5. **Write `provenance.md`** beside `golden.json` — verbatim quotes, attribution, source URL, fix commit hash. This is the chamber-busting evidence trail. The grader doesn't read it but auditors will.
6. **Set `oracle_type: external_authority`** in `task.json` and `golden.json`. Use `oracle_type: physics_first_principles` only for hand-constructed seed fixtures, `external_tool` for OpenSTA/PrimeTime-graded cases, `external_authority` for human-authoritative cases.
7. **Validate** with `python benchmarks/timing_diagnosis/run.py validate`.
8. **Smoke test** with a mock-mode agent run (see `tests/test_timing_diagnosis_agent.py` for the pattern) and confirm a plausible answer grades PASS.

The pre-verified candidate corpus from research-Claude's pass is in `docs/PLAN.md` under "Authority cases queued" — 16 cases past `authority_001_ol_1371_hold_repair_setup_conflict` (which is wired). See that file for the next batch to wire and which need attention.

## Attribution obligations

When the bench publishes externally (LinkedIn, paper, etc.), every authority case carries an attribution debt to the named maintainers whose diagnoses became the gold answer. Examples already in scope:

- James Cherry (jjcherry56 / parallaxsw) — author of OpenSTA, multiple OL/OSTA cases
- Anton Blanchard (antonblanchard) — IBM / Linux kernel
- Mohamed Gaber (donn) — OpenLane lead
- Cho Moon (precisionmoon) — Precision Inno / OpenROAD
- Eder Matheus Monteiro (eder-matheus) — UFRGS / OpenROAD
- Peter Gadfort (gadfort) — OpenSTA contributor
- Matt Liberty (maliberty) — OpenROAD core / UCSD
- Alan Mishchenko — ABC / UC Berkeley (via correspondence quoted in OL-1523)

When the time comes, build a `NOTICE.md` at the repo root collecting these from the `provenance.md` files. Pre-publication courtesy ping at minimum to Cherry, Liberty, Donn, and Kahng (whose METRICS2.1 schema we align with).

## What about the chamber on this very file?

This document was drafted by Claude in a multi-agent session. It encodes process the three of us (Mani + Claude + Codex) converged on. Future agents reading this should be empowered to disagree with anything here based on external evidence. The rule isn't "follow this file"; the rule is "the things in here have to survive falsification." If you find something here that's wrong, edit it and explain why.
