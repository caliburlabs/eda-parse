# Task

Diagnose why this OpenLane/OpenSTA reproducer hangs during `report_clock_skew`.

The visible inputs preserve three load-bearing pieces of the public issue:

- `input/standalone/bug.tcl` is the maintainer-packaged standalone STA testcase.
- `input/standalone/sta_clock_skew_excerpt.tcl` is the relevant OpenLane source excerpt,
  including the comment that blames clockless designs.
- `input/thread_excerpt.md` archives the public issue discussion around that claim and
  the eventual maintainer resolution.

Your job is to decide whether the source comment is correct, identify the actual trigger
for the hang, and propose one concrete next step that reflects the fix path that closed the
issue.

Return only JSON via the `final_answer` tool, matching the standard timing-diagnosis answer
schema:

```json
{
  "failing_stage": "...",
  "violation_type": "...",
  "root_cause": "...",
  "clock": "...",
  "evidence": ["input/path:line", "..."],
  "next_action": "...",
  "confidence": 0.0
}
```

Notes:

- This case has no required numeric fields.
- The grader expects evidence that you inspected both the source excerpt and the archived
  public issue thread.
- The next action should name the OpenROAD fix commit that resolves the hang.
