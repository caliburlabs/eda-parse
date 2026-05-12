# Provenance - authority_002_ol_958_report_clock_skew_feedback_loop

Generated from the rich external-authority curation payload. The grader-facing
`golden.json` is derived from an explicit overlay; this file preserves the
human-auditable quote trail and the richer case notes.

## Source

- Rich case id: `OL-958`
- URL: https://github.com/The-OpenROAD-Project/OpenLane/issues/958
- State: closed
- State evidence: in-thread fix-commit by jjcherry56
- Category: tool-hang / wrong-source-comment
- Difficulty: hard
- Tier: `1`

## Verbatim diagnoses

> **jjcherry56** (James Cherry - OpenSTA author / Parallax Software):
>
> OpenROAD e3315ba41 fixes it on our end
>
> Source: issue thread comment

> **jjcherry56** (James Cherry - OpenSTA author / Parallax Software):
>
> @Manarabdelaty this comment is wrong. report_clock_skew works just find if there are no clocks defined. > # OR hangs if this command is run on clockless designs > The issue has nothing to do with whether or not clocks are defined. It is a bug dealing with combinational feedback loops. OpenSTA has already been fixed but has not been integrated into openroad yet because of all the required verification steps.
>
> Source: issue thread comment

## Resolution metadata

- `state`: closed
- `state_evidence`: in-thread fix-commit by jjcherry56
- `category`: tool-hang / wrong-source-comment
- `difficulty`: hard
- `tier`: 1
- `fix_commit`: OpenROAD e3315ba41
- `adversarial_property`: The fix-commit-bearing source file contains an incorrect comment that an agent prone to trusting source comments will adopt as the diagnosis. Tests source-comment-vs-maintainer-comment priority.

## Artifact references from curation

- `run3_sta_packaged.zip`: https://github.com/The-OpenROAD-Project/OpenLane/files/8151319/run3_sta_packaged.zip
- `bug.zip`: https://github.com/The-OpenROAD-Project/OpenLane/files/8155671/bug.zip

## Human grading notes from curation

- Agent must REJECT the source comment in sta.tcl claiming clockless designs cause the hang
- Identifies combinational feedback loops as the actual cause
- Identifies OpenSTA STA traversal as the location
- Bonus: names commit e3315ba41

## Raw curation payload

```json
{
  "adversarial_property": "The fix-commit-bearing source file contains an incorrect comment that an agent prone to trusting source comments will adopt as the diagnosis. Tests source-comment-vs-maintainer-comment priority.",
  "case_id": "OL-958",
  "category": "tool-hang / wrong-source-comment",
  "difficulty": "hard",
  "fix_commit": "OpenROAD e3315ba41",
  "grading_rubric": [
    "Agent must REJECT the source comment in sta.tcl claiming clockless designs cause the hang",
    "Identifies combinational feedback loops as the actual cause",
    "Identifies OpenSTA STA traversal as the location",
    "Bonus: names commit e3315ba41"
  ],
  "input_artifacts": [
    {
      "filename": "run3_sta_packaged.zip",
      "reachable_unverified": true,
      "url": "https://github.com/The-OpenROAD-Project/OpenLane/files/8151319/run3_sta_packaged.zip"
    },
    {
      "filename": "bug.zip",
      "reachable_unverified": true,
      "url": "https://github.com/The-OpenROAD-Project/OpenLane/files/8155671/bug.zip"
    }
  ],
  "misleading_source_artifact": {
    "actual_cause": "combinational feedback loops",
    "file": "sta.tcl",
    "wrong_comment": "# OR hangs if this command is run on clockless designs"
  },
  "source_url": "https://github.com/The-OpenROAD-Project/OpenLane/issues/958",
  "state": "closed",
  "state_evidence": "in-thread fix-commit by jjcherry56",
  "tier": 1,
  "verbatim_diagnoses": [
    {
      "author": "jjcherry56",
      "author_name": "James Cherry",
      "quote": "OpenROAD e3315ba41 fixes it on our end",
      "role": "OpenSTA author / Parallax Software",
      "source": "issue thread comment"
    },
    {
      "author": "jjcherry56",
      "author_name": "James Cherry",
      "quote": "@Manarabdelaty this comment is wrong. report_clock_skew works just find if there are no clocks defined. > # OR hangs if this command is run on clockless designs > The issue has nothing to do with whether or not clocks are defined. It is a bug dealing with combinational feedback loops. OpenSTA has already been fixed but has not been integrated into openroad yet because of all the required verification steps.",
      "role": "OpenSTA author / Parallax Software",
      "source": "issue thread comment"
    }
  ]
}
```
