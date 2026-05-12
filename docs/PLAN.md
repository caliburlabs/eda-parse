# Plan, current state, and open work

This is the living roadmap. Update it as state changes — especially when something here no longer matches reality.

## Where we are (2026-05-11)

**Versions shipped:**
- `eda-parse v0.2.1` — Liberty + LEF + SDC parsers, LangChain loaders, `workflow_testbench.py` acceptance test. Repo public on `github.com/caliburlabs/eda-parse`.
- `benchmarks/timing_diagnosis/` v0 — harness (Codex), agent runner (Claude), three physics-tier seed tasks, one external-authority case (`authority_001_ol_1371_hold_repair_setup_conflict`).

**What works end-to-end:**
- Real-fixture parser tests pass against SKY130, NanGate FreePDK45, ASAP7 (all redistributable).
- `python benchmarks/timing_diagnosis/run.py validate` PASS for all 4 tasks.
- Mock-driven agent → grader closes the loop on physics_001 and authority_001 with PASS at 100%.
- 42/42 pytest, ruff clean, mypy `--strict` clean.

**What is *not* yet done:**
- The real Anthropic API has never been called against any authority case. Every loop closure so far is mock-mode. **The actual chamber-check fires when we run real Claude against a sealed case.**
- 16 verified candidate authority cases from research-Claude's curation pass are not yet wired to the bench. The pattern is established (see `authority_001_ol_1371_*`); the work is mechanical.
- OpenSTA-backed `external_tool` oracle type exists in the schema but no case uses it.
- Format coverage gaps: DEF, VCD, SPEF parsers planned but not built.

## What's where

```
src/eda_parse/                    # the parser library — Liberty, LEF, SDC
benchmarks/timing_diagnosis/      # the bench
  agent.py                        # Claude agent runner with tool loop
  harness.py                      # grader (load_task, grade_payload, iter_tasks)
  run.py                          # CLI: list / validate / grade
  tasks/
    physics_001..003/             # seed fixtures
    authority_001_ol_1371_*/      # first real authority case (OpenLane #1371)
  templates/authority_case/       # template for new authority case
docs/
  PLAN.md                         # this file
  bench-design.md                 # bench philosophy + oracle tiers
  golden-schema.md                # exact spec for hidden_oracle/golden.json
  why.md                          # market framing (SemiAnalysis 50%/20% gap)
  dev-log.md                      # chronological session log
  formats/{liberty,lef,sdc}.md
AGENTS.md                         # operating manual for agents working in this repo
README.md                         # public README — quickstart + format status
```

## Authority cases queued (16 verified candidates, not yet wired)

Research-Claude verified these in the chamber-check pass on 2026-05-11. Verbatim quotes confirmed against live GitHub issues. Schema translation needed (their rich-format goldens are not grader-compatible — see `docs/golden-schema.md`). Each needs:

1. Download artifacts to `input/`, strip oversized files
2. Write `task.json` (oracle_type: external_authority)
3. Write grader-shaped `golden.json` (per `docs/golden-schema.md`)
4. Write `provenance.md` with verbatim quotes + attribution + source URL
5. Write `prompt.md`
6. `run.py validate` + mock-mode smoke test

The 16 candidates, by tier:

**Tier 1 — strong (10 left after authority_001 already wired):**
- `OL-1491` — regression diagnosis (OpenLane PR #1485 broke LIB_SYNTH path; donn names revert)
- `OR-4634` — CTS segfault, precisionmoon names PR #4607 fix
- `OR-1879` — set_max_delay overlap, Cherry names OpenSTA c7debe5
- `OL-958` — `report_clock_skew` hangs on combinational feedback loops; Cherry rejects misleading source comment
- `OR-4833` — misleading-title case (antenna repair fingered, eder-matheus shows real bottleneck is `report_metrics`)
- `OSTA-60` — NaN in Power.cc:855, Cherry commit `bdd74687` "power nan-proofing"
- `OR-6181` — clock-latency mismatch (megaboom), Cherry commit `a82361ce`
- `OL-1523` — Yosys `rewrite` pass broken, replace with `drw` (per Mishchenko correspondence)
- `OL-1833` — SDC audit case (missing `set_propagated_clock`)
- `OR-1940` — DRT missing met3 min-area rule, cross-tool confirmation by Magic+KLayout

**Tier 2 — medium (4):**
- `OR-3759` — feature-history (clock latency modeling, two-PR sequence #4607 → #4678)
- `OR-4751` — misleading title (CTS skew blamed; `repair_clock_nets` is offender)
- `OL-1032` — units-vs-values UX bug (not a numerical bug despite appearance)
- `OR-2207` — antenna repair, multiple plausible mitigations, no consensus

**Tier 3 — calibration (3):**
- `OR-4359` — feature-or-bug ambiguity, stale-closed without fix
- `OL-1124` — multi-part issue, only documentation sub-issue resolved
- `OR-2207` — also calibration-eligible

(Yes, the totals don't quite add to 17 because of overlap and reshape; net committable is 16 past `authority_001` per research-Claude's pass.)

Full per-case rich metadata (verbatim quotes, fix commits, attribution) lives in research-Claude's curation pass output. When wiring a case, the rich format → grader format translation is the load-bearing step. The pattern from `authority_001_ol_1371_*/hidden_oracle/{golden.json, provenance.md}` is the template.

## Open work, ranked by what unblocks the most

### Tier 1 — needed for the bench to be real

1. **Real Anthropic API run against `authority_001_ol_1371_*`.** The first real chamber-check moment. ~$0.10–0.50 per run on `claude-opus-4-7`. Until this fires, every claim about agent capability is mock-mode plumbing. **Mani decides when.**
2. **Wire 5–10 more authority cases** from the verified backlog, prioritising adversarial-shape cases (`OL-958` and `OR-4833` — agent has to dig past misleading evidence). Smallest credible corpus for a published bench.
3. **Build a small converter script** that takes research-Claude's rich-format curation output and emits grader-shaped `golden.json` + `provenance.md`. Replaces hand-translation for the remaining ~10 cases. Lives at `tools/convert_curation_to_golden.py` (doesn't exist yet).
4. **Run agent against multiple models** (`claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`) on the same corpus. First per-model scorecard.

### Tier 2 — extends the bench

5. **Install OpenSTA** locally (or on a separate runner) and wire one case under `oracle_type: external_tool`. Closes the "tool oracle" half that's been declared but not used.
6. **DEF parser** (issue #1) — extends format coverage past Liberty/LEF/SDC. Uses same hand-rolled tokeniser pattern as the existing parsers.
7. **VCD parser** (issue #2) — IEEE 1364, ASCII waveforms. Generated from open RTL via Verilator/iverilog.
8. **SPEF parser** (issue #3) — fixture already in `tests/fixtures/spef/gcd_sky130hd.spef`.

### Tier 3 — strategic/operational

9. **Authority NOTICE file** at repo root listing all maintainer attributions from `provenance.md` files across the corpus. Becomes a publish-day requirement; cheap to maintain incrementally.
10. **Pre-publication courtesy outreach plan** — at minimum Cherry, Liberty, Donn, Kahng. Drafted but not sent.
11. **LinkedIn / external announcement** — gated on (a) at least 5 wired authority cases, (b) at least one real-API scorecard, (c) NOTICE file in place.
12. **wafer.space watch** — the open-PDK ecosystem we depend on has a single point of failure. Track its activity periodically.

## Things to *not* do

- Don't extend the grader schema to handle "richer" golden formats. Put rich content in `provenance.md`. The grader's contract is the API; changing it touches every case.
- Don't add proprietary-PDK fixtures, ever. SKY130 / FreePDK45 / ASAP7 only.
- Don't commit oversized artifacts blindly. The OL-1371 wiring stripped a 2.2MB synthesized netlist; future authority cases should also trim the inputs the agent doesn't need for diagnosis.
- Don't run real-API agent calls in CI. Mock-mode only in CI; real runs are explicit, manual, and budgeted.
- Don't delete or rewrite Codex's prose without surfacing the change first. Multi-agent coordination matters.

## Memory + handoff state for future agents

The full handoff context lives in three places. New agents picking up work should read all three:

1. **`AGENTS.md`** at repo root — the operating manual.
2. **This file (`docs/PLAN.md`)** — the roadmap.
3. **`docs/dev-log.md`** — chronological narrative of what was done in each session and why.

Plus the durable instruction set in Claude's auto-memory at `~/.claude/projects/-Users-manirashahmadi-phasegrad/memory/`. Relevant entries:

- `feedback_chamber_check.md` — the chamber-check protocol
- `project_two_sided_artifact.md` — bench + subject co-evolve
- `project_eda_market_context.md` — SemiAnalysis primer, competitive landscape, 50%/20% gap
- `reference_cmc_eda_cloud.md` — CMC SSH playbook, PDK-redistribution rules
- `feedback_artifact_pulled.md` — Mani navigates by artifacts; "no direction" = between artifacts
- `feedback_make_then_understand.md` — production arrives before comprehension; ship artifacts, don't deliberate

If those memory files are not accessible (different account, different host, etc.) the principles are still encoded in `AGENTS.md` and `docs/bench-design.md`. Memory is a convenience, not a dependency.
