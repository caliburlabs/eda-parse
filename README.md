# eda-parse

[![ci](https://github.com/caliburlabs/eda-parse/actions/workflows/ci.yml/badge.svg)](https://github.com/caliburlabs/eda-parse/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

`eda-parse` is an MIT-licensed Python library for turning common EDA file formats into structured, LLM-friendly documents. It parses real Liberty, LEF, and SDC files into typed chunks with metadata, while preserving access to the underlying AST for users who need lower-level inspection.

The immediate use case is retrieval over chip-design artifacts: standard-cell libraries, physical abstracts, constraints, waveforms, timing reports, and tool outputs. The first releases focus on Liberty, LEF, and SDC because those formats together give useful coverage across timing, power, physical design, and design-intent context.

## Install

```bash
pip install eda-parse
```

For LangChain loaders:

```bash
pip install "eda-parse[langchain]"
```

## Quickstart

### Liberty

```python
from eda_parse.parsers import liberty

doc = liberty.parse("sky130_fd_sc_hd__tt_025C_1v80.lib")
print(doc.metadata["cell_count"])
print(doc.chunks[0].metadata["pin_directions"])
```

### LEF

```python
from eda_parse.parsers import lef

doc = lef.parse("sky130_fd_sc_hd_merged.lef")
print(doc.metadata["macro_count"])
print(doc.chunks[0].metadata["pin_count"])
```

### SDC

```python
from eda_parse.parsers import sdc

doc = sdc.parse("gcd.sdc")
print(doc.metadata["clock_count"], doc.metadata["input_delay_count"])
clocks = [c for c in doc.chunks if c.kind == "clock"]
print(clocks[0].metadata)  # → {'period': 5.0, 'ports': '[get_ports clk]', ...}
```

### LangChain

```python
from eda_parse.loaders import LibertyLoader, LEFLoader, SDCLoader

docs = LibertyLoader("sky130hd_tt.lib.gz").load()
print(docs[0].page_content)
```

### Demo: structured QA over a real corpus

```bash
python examples/demo_corpus_qa.py
```

Answers five concrete questions ("What clocks exist?", "What cells/macros are available?", "What PVT corner is this characterized for?", plus a cross-document sanity check) without any embedding model or LLM. Pure metadata filtering on what the parsers extracted. The optional `--with-rag` flag layers a sentence-transformer + FAISS retriever on top for the genuinely open-ended questions.

### Acceptance testbench

```bash
python benchmarks/workflow_testbench.py
```

Runs the public workflow acceptance test: parse SKY130 Liberty + SKY130 merged LEF + gcd SDC, verify known extracted facts, verify 873 retrieval chunks, answer the five concrete workflow questions, and fail if the corpus parse exceeds the ingest budget. See `docs/testbench.md`.

### Timing-diagnosis harness

```bash
python benchmarks/timing_diagnosis/run.py list
python benchmarks/timing_diagnosis/run.py validate
```

Starts the agent-benchmark side of the project: frozen timing-diagnosis tasks with visible inputs and hidden golden answers. The checked-in seed tasks are first-principles harness fixtures; the intended external checks are OpenSTA/PrimeTime-generated tasks and sealed authority cases. See `benchmarks/timing_diagnosis/README.md`.

## Document Model

Every parser returns a `ParsedDocument`:

```python
{
    "content": str,
    "metadata": dict,
    "source_format": "liberty" | "lef" | "def" | "vcd" | "sdc" | "spef",
    "chunks": list,
    "raw": object,
}
```

Chunks are semantic retrieval units. Liberty emits one chunk per `cell`; LEF emits one chunk per `MACRO`. Each chunk carries human-readable content plus structured metadata for filtering and analysis.

## Format Status

| Format | Status | Chunking | Fixture validation |
| --- | --- | --- | --- |
| Liberty `.lib`, `.lib.gz` | Implemented | `cell` | ASAP7, SKY130 |
| LEF `.lef`, `.tlef` | Implemented | `MACRO` | SKY130 |
| SDC `.sdc` | Implemented | one chunk per constraint (clock, input_delay, output_delay, false_path, multicycle_path, clock_groups, …) | SKY130 (gcd) |
| DEF | Planned | components, nets, rows | Not yet shipped |
| VCD | Planned | scopes, signals, transitions | Not yet shipped |
| SPEF | Planned | nets, parasitics | Fixture present, parser pending |

The committed fixtures are redistributable public files from OpenSTA and OpenROAD-flow-scripts. CMC-restricted PDK files, including TSMC and Cadence GPDK kits, must not be committed.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev,langchain]"
ruff check src tests benchmarks
mypy src/eda_parse
pytest -ra
python benchmarks/workflow_testbench.py
python benchmarks/timing_diagnosis/run.py validate
```

## Contributing

Contributions should include:

1. A parser or metadata improvement with type hints.
2. Tests against redistributable real EDA files when possible.
3. Fixture provenance in `tests/fixtures/README.md`.
4. Documentation under `docs/formats/` for new format coverage.

Do not commit proprietary PDKs, vendor tool outputs covered by license restrictions, customer design files, or CMC-restricted artifacts.

## License

MIT. See [LICENSE](LICENSE).
