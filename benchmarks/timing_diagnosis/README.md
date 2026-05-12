# Timing-Diagnosis Agent Harness

This is the first agent-benchmark surface layered on top of `eda-parse`.

The job is not to prove the parser works. The job is to test whether an agent can inspect timing artifacts, diagnose the failure, cite evidence, and propose the next concrete engineering action.

## Oracle Model

Every task has the same visible/hidden split:

```text
task/
  task.json
  prompt.md
  input/
    design.v
    constraints.sdc
    reports/timing_report.rpt
  hidden_oracle/
    golden.json
```

The agent receives `prompt.md` and `input/`. The grader receives `hidden_oracle/golden.json`.

We support three oracle sources:

| Oracle type | Meaning | Use |
|-------------|---------|-----|
| `physics_first_principles` | Controlled case where timing numbers and diagnosis follow from fixed timing arithmetic. | Fast seed tests; useful for harness development. |
| `external_tool` | Golden answer derived from OpenSTA, PrimeTime, Genus, Innovus, or another real EDA tool. | Public physics oracle once OpenSTA tasks are regenerated; private CMC oracle when available. |
| `external_authority` | Golden answer sealed by a human or a trusted public issue resolution before the agent sees the case. | Flodraulic-style external check; catches context errors a tool report may not. |

The three checked-in `physics_*` tasks are first-principles harness fixtures. They are useful for developing the contract, but they are not a substitute for an OpenSTA/PrimeTime-generated corpus. The next high-signal case should be an `external_authority` bundle chosen and sealed outside this repo.

## Agent Answer Schema

Agents should emit JSON:

```json
{
  "failing_stage": "static_timing",
  "violation_type": "setup",
  "root_cause": "clock_period_too_short",
  "clock": "core_clk",
  "declared_period_ns": 1.0,
  "worst_slack_ns": -0.42,
  "minimum_passing_period_ns": 1.42,
  "evidence": [
    "input/constraints.sdc:3",
    "input/reports/timing_report.rpt:26"
  ],
  "next_action": "Relax the core_clk period to at least 1.42 ns or optimize the critical path.",
  "confidence": 0.82
}
```

Goldens may require additional task-specific numeric keys such as `unconstrained_input_count`. Keep them as top-level snake_case fields so the grader can compare them directly.

## Commands

```bash
python benchmarks/timing_diagnosis/run.py list
python benchmarks/timing_diagnosis/run.py validate
python benchmarks/timing_diagnosis/run.py grade benchmarks/timing_diagnosis/tasks/physics_001_overconstrained_clock answer.json
```
