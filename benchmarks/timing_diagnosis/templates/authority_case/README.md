# Authority Case Template

Use this for a sealed CMC or public-issue case.

1. Copy this directory to `benchmarks/timing_diagnosis/tasks/authority_001_<short_name>/`.
2. Put only agent-visible artifacts under `input/`.
3. Write the diagnosis outside the agent loop first.
4. Fill `hidden_oracle/golden.json` from that sealed diagnosis.
5. Do not expose `hidden_oracle/` to the agent.

Minimum hidden golden fields:

```json
{
  "task_id": "authority_001_example",
  "oracle_type": "external_authority",
  "required_exact": {
    "failing_stage": "static_timing",
    "root_cause": "clock_period_too_short"
  },
  "required_numeric": {},
  "required_evidence": ["constraints.sdc", "timing_report.rpt"],
  "required_next_action_terms": ["relax", "period"]
}
```

