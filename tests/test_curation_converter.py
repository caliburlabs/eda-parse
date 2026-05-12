from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
CONVERTER_PATH = ROOT / "tools" / "convert_curation_to_golden.py"

SAMPLE_CURATION = """
## Committable golden.json content

### tasks/OL-1371/hidden_oracle/golden.json (sample heading suffix)

```json
{
  "case_id": "OL-1371",
  "source_url": "https://github.com/The-OpenROAD-Project/OpenLane/issues/1371",
  "state": "closed",
  "state_evidence": "in-thread fix-commit announcement by jjcherry56",
  "category": "timing-repair-strategy",
  "difficulty": "medium",
  "tier": 1,
  "verbatim_diagnoses": [
    {
      "author": "jjcherry56",
      "author_name": "James Cherry",
      "role": "OpenSTA author / Parallax Software",
      "quote": "fixed in openroad 79313e90d",
      "source": "issue thread comment"
    }
  ],
  "fix_commit": "openroad 79313e90d",
  "fix_file_path": "src/rsz/src/RepairHold.cc",
  "user_workaround": "set ::env(GLB_RESIZER_ALLOW_SETUP_VIOS) 1",
  "input_artifacts": [
    {
      "filename": "16-resizer.log",
      "url": "https://example.invalid/16-resizer.log",
      "reachable_unverified": true
    }
  ],
  "grading_rubric": [
    "Identifies the setup-preservation guard",
    "Names the env-var workaround"
  ]
}
```
"""

SAMPLE_OVERLAY = {
    "OL-1371": {
        "task_id": "authority_001_ol_1371_hold_repair_setup_conflict",
        "required_exact": {
            "violation_type": "hold",
            "root_cause": ["hold_repair_blocked_by_setup_violations"],
        },
        "required_numeric": {},
        "required_evidence": ["16-resizer.log", "RSZ-0064"],
        "required_next_action_terms": ["GLB_RESIZER_ALLOW_SETUP_VIOS"],
        "provenance": {
            "status": "github_issue_maintainer_resolution",
            "converter_test_marker": "overlay-wins",
            "state": "verified-closed",
            "state_evidence": "overlay state correction",
        },
    }
}


def _load_converter() -> ModuleType:
    spec = importlib.util.spec_from_file_location("curation_converter", CONVERTER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_cases_from_markdown() -> None:
    converter = _load_converter()

    cases = converter.extract_cases_from_markdown(SAMPLE_CURATION)

    assert set(cases) == {"OL-1371"}
    assert cases["OL-1371"]["fix_commit"] == "openroad 79313e90d"


def test_build_golden_merges_rich_provenance_with_overlay() -> None:
    converter = _load_converter()
    rich_case = converter.extract_cases_from_markdown(SAMPLE_CURATION)["OL-1371"]

    golden = converter.build_golden(rich_case, SAMPLE_OVERLAY["OL-1371"])

    assert golden["task_id"] == "authority_001_ol_1371_hold_repair_setup_conflict"
    assert golden["oracle_type"] == "external_authority"
    assert golden["required_evidence"] == ["16-resizer.log", "RSZ-0064"]
    assert golden["provenance"]["fix_commit"] == "openroad 79313e90d"
    assert golden["provenance"]["converter_test_marker"] == "overlay-wins"
    assert golden["provenance"]["authorities"] == [
        {
            "github": "jjcherry56",
            "name": "James Cherry",
            "role": "OpenSTA author / Parallax Software",
        }
    ]


def test_convert_cases_writes_golden_and_provenance(tmp_path: Path) -> None:
    converter = _load_converter()
    rich_case = converter.extract_cases_from_markdown(SAMPLE_CURATION)

    results = converter.convert_cases(
        rich_case,
        SAMPLE_OVERLAY,
        tasks_root=tmp_path,
    )

    assert len(results) == 1
    hidden_oracle = (
        tmp_path
        / "authority_001_ol_1371_hold_repair_setup_conflict"
        / "hidden_oracle"
    )
    golden = json.loads((hidden_oracle / "golden.json").read_text(encoding="utf-8"))
    provenance = (hidden_oracle / "provenance.md").read_text(encoding="utf-8")

    assert golden["required_next_action_terms"] == ["GLB_RESIZER_ALLOW_SETUP_VIOS"]
    assert "# Provenance - authority_001_ol_1371_hold_repair_setup_conflict" in provenance
    assert "- State: verified-closed" in provenance
    assert "- State evidence: overlay state correction" in provenance
    assert "fixed in openroad 79313e90d" in provenance
    assert "Human grading notes from curation" in provenance
