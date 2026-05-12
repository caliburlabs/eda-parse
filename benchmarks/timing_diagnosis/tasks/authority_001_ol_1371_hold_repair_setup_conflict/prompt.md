# Task

Diagnose why this OpenLane run cannot close hold timing.

The artifacts under `input/` are taken from a real failing run on the
`ycr4_iconnect` design (sky130hd, OpenLane circa late 2022). The
post-resizer log (`16-resizer.log`) reports unresolved hold violations
after the routing-stage timing repair. The full reproducer — the
constraint files, the OpenROAD scripts the resizer ran, the OpenLane env
the run used — is under `input/reproducer/`.

Your job is to inspect the artifacts, identify the algorithmic mechanism
that prevents hold repair from converging here, and propose one concrete
flow-level change that would let it succeed.

Return only JSON via the `final_answer` tool, matching the standard
timing-diagnosis answer schema:

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

- This task has no required numeric fields (`declared_period_ns`,
  `worst_slack_ns`, `minimum_passing_period_ns`) — set them only if you
  can derive them from the artifacts; the grader does not require them.
- The grader checks for the presence of specific evidence files and
  specific keywords in `next_action`. Cite the OpenLane environment
  variable that controls the relevant resizer behavior.
- The diagnosis here is about the *interaction* between setup repair and
  hold repair, not a single broken constraint or a single broken cell.
