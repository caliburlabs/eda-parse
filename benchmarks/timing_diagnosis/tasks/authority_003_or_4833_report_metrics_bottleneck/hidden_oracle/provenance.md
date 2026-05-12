# Provenance - authority_003_or_4833_report_metrics_bottleneck

Generated from the rich external-authority curation payload. The grader-facing
`golden.json` is derived from an explicit overlay; this file preserves the
human-auditable quote trail and the richer case notes.

## Source

- Rich case id: `OR-4833`
- URL: https://github.com/The-OpenROAD-Project/OpenROAD/issues/4833
- State: closed
- State evidence: Live GitHub issue state re-verified as CLOSED on 2026-05-12.
- Category: misleading-title / surface-vs-real-bottleneck
- Difficulty: hard
- Tier: `1`

## Verbatim diagnoses

> **eder-matheus** (Eder Matheus Monteiro - UFRGS / OpenROAD core dev):
>
> I found the problem lies in report_metrics, not estimate_parasitics. I didn't notice it when editing the script to get the runtimes, but now I see this: * 54 minutes in GRT + incremental * 4 minutes in repair_antennas + check_antennas * 2.5 minutes in estimate_parasitics. The remaining runtime is only with report_metrics, which is about 2 hours.
>
> Source: issue thread comment

> **maliberty** (Matt Liberty - OpenROAD core / UCSD):
>
> @luis201420 is reworking antenna repair so he can use this as a test for his work.
>
> Source: issue thread comment

## Resolution metadata

- `state`: closed
- `state_evidence`: Live GitHub issue state re-verified as CLOSED on 2026-05-12.
- `category`: misleading-title / surface-vs-real-bottleneck
- `difficulty`: hard
- `tier`: 1
- `fix_pr`: OpenROAD-flow-scripts #2063 (parallelization of check_antennas and repair_antennas)
- `actual_bottleneck`: report_metrics
- `adversarial_property`: Issue title points away from the real cause. Tests evidence-based reasoning vs. surface framing.
- `verification_note`: The rich curation payload carried an earlier 'closed inferred' caveat. Live re-verification on 2026-05-12 removed that ambiguity.

## Artifact references from curation

- `BoomTile-asap7-base.tar.gz`: https://drive.google.com/file/d/1YjhsuuE8w0GLaL_opM6-s5izSQq0ML4H/view?usp=sharing

## Human grading notes from curation

- Agent must NOT adopt the issue title's framing ('antenna repair is slow')
- Identifies report_metrics as the actual bottleneck (~2 hours of the 2-hour wallclock)
- Bonus: per-stage runtime breakdown matching the four-stage decomposition

## Raw curation payload

```json
{
  "actual_bottleneck": "report_metrics",
  "adversarial_property": "Issue title points away from the real cause. Tests evidence-based reasoning vs. surface framing.",
  "case_id": "OR-4833",
  "category": "misleading-title / surface-vs-real-bottleneck",
  "difficulty": "hard",
  "fix_pr": "OpenROAD-flow-scripts #2063 (parallelization of check_antennas and repair_antennas)",
  "grading_rubric": [
    "Agent must NOT adopt the issue title's framing ('antenna repair is slow')",
    "Identifies report_metrics as the actual bottleneck (~2 hours of the 2-hour wallclock)",
    "Bonus: per-stage runtime breakdown matching the four-stage decomposition"
  ],
  "input_artifacts": [
    {
      "filename": "BoomTile-asap7-base.tar.gz",
      "format": "external_drive_link",
      "reachable_unverified": true,
      "url": "https://drive.google.com/file/d/1YjhsuuE8w0GLaL_opM6-s5izSQq0ML4H/view?usp=sharing"
    }
  ],
  "issue_title": "Speed up global route, antenna repair in particular",
  "runtime_breakdown_authoritative": {
    "GRT + incremental": "54 min",
    "estimate_parasitics": "2.5 min",
    "repair_antennas + check_antennas": "4 min",
    "report_metrics": "~120 min"
  },
  "source_url": "https://github.com/The-OpenROAD-Project/OpenROAD/issues/4833",
  "state": "closed (inferred via ORFS PR #2063 from earlier listing; not directly verified from main thread fetch)",
  "state_evidence": "eder-matheus in-thread parallelization work + listing snippet 'eder-matheus closed this as completed in OpenROAD-flow-scripts#2063'",
  "tier": 1,
  "verbatim_diagnoses": [
    {
      "author": "eder-matheus",
      "author_name": "Eder Matheus Monteiro",
      "quote": "I found the problem lies in report_metrics, not estimate_parasitics. I didn't notice it when editing the script to get the runtimes, but now I see this: * 54 minutes in GRT + incremental * 4 minutes in repair_antennas + check_antennas * 2.5 minutes in estimate_parasitics. The remaining runtime is only with report_metrics, which is about 2 hours.",
      "role": "UFRGS / OpenROAD core dev",
      "source": "issue thread comment"
    },
    {
      "author": "maliberty",
      "author_name": "Matt Liberty",
      "quote": "@luis201420 is reworking antenna repair so he can use this as a test for his work.",
      "role": "OpenROAD core / UCSD",
      "source": "issue thread comment"
    }
  ]
}
```
