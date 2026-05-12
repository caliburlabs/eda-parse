# Workflow Testbench

The testbench is the acceptance workflow for `eda-parse`. It is stricter than the demo:

1. Parse a fixed real public corpus.
2. Check known facts extracted from each artifact.
3. Check retrieval chunk counts and chunk kinds.
4. Answer concrete workflow questions from parser metadata.
5. Fail if the corpus parse exceeds the configured ingest budget.

Run it from the repository root:

```bash
python benchmarks/workflow_testbench.py
```

For machine-readable output:

```bash
python benchmarks/workflow_testbench.py --json reports/open_corpus.json
```

Current corpus:

- SKY130 Liberty: `tests/fixtures/liberty/sky130hd_tt.lib.gz`
- SKY130 merged LEF: `tests/fixtures/lef/sky130_fd_sc_hd_merged.lef`
- SKY130 gcd SDC: `tests/fixtures/sdc/gcd_sky130hd.sdc`

The pass/fail checks are intentionally concrete: cell count, pin count, macro count, macro class distribution, clock count, resolved clock period, chunk count, and cross-document target matching. This is the public proxy for value: the library must reliably turn real EDA artifacts into structured facts and retrieval units.

This does not try to mimic any private lab's internal benchmark. Private teams will have their own formats, scale, and golden tool reports. The public testbench gives them a reproducible baseline they can extend with their own artifacts without changing the parser API.
