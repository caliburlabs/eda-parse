# eda-parse

`eda-parse` is an MIT-licensed Python library for turning common EDA file formats into structured, LLM-friendly documents. It parses real Liberty and LEF files into typed chunks with metadata, while preserving access to the underlying AST for users who need lower-level inspection.

The immediate use case is retrieval over chip-design artifacts: standard-cell libraries, physical abstracts, constraints, waveforms, timing reports, and tool outputs. The first release focuses on Liberty and LEF because those formats give useful coverage across timing, power, and physical-design context.

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

### LangChain

```python
from eda_parse.loaders import LibertyLoader

docs = LibertyLoader("sky130hd_tt.lib.gz").load()
print(docs[0].page_content)
```

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
| DEF | Planned | components, nets, rows | Not yet shipped |
| SDC | Planned | clocks, constraints, exceptions | Fixture present, parser pending |
| VCD | Planned | scopes, signals, transitions | Not yet shipped |
| SPEF | Planned | nets, parasitics | Fixture present, parser pending |

The committed fixtures are redistributable public files from OpenSTA and OpenROAD-flow-scripts. CMC-restricted PDK files, including TSMC and Cadence GPDK kits, must not be committed.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev,langchain]"
ruff check src tests
mypy src/eda_parse
pytest -ra
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
