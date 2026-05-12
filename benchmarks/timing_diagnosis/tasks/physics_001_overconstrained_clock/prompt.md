# Task

Diagnose the timing failure in this run.

Use the files under `input/`. Return only JSON matching the timing-diagnosis answer schema:

```json
{
  "failing_stage": "...",
  "violation_type": "...",
  "root_cause": "...",
  "clock": "...",
  "declared_period_ns": 0.0,
  "worst_slack_ns": 0.0,
  "minimum_passing_period_ns": 0.0,
  "evidence": ["path:line"],
  "next_action": "...",
  "confidence": 0.0
}
```

Include `minimum_passing_period_ns` when the report gives enough information to infer the relaxed passing period.
