# eda-parse development log

A short chronological record of implementation decisions that are useful to future contributors.

## 2026-05-11 kickoff

Goal: scaffold the repo and ship the weekend-1 surface:

- Liberty parser
- LEF parser
- Shared `ParsedDocument` and `Chunk` interface
- LangChain loaders
- Real fixture tests
- README and CI

## Fixture policy

The original validation plan included proprietary academic/CMC PDK files. Those files are useful for private validation but cannot be committed. Public tests use redistributable open fixtures instead:

- SKY130 via public OpenSTA/OpenROAD fixture paths
- ASAP7 small Liberty files via OpenSTA fixtures

Private PDK validation should stay out of the repo. If proprietary kits are used, only summary statistics such as cell counts, macro counts, parser timings, and pass/fail status should be recorded.

## Scaffolding choices

- `src/` layout to avoid accidental local imports.
- `hatchling` build backend.
- Python 3.10+.
- Hard dependency: `pydantic`.
- Optional LangChain dependency: `langchain-core`.
- Hand-rolled recursive-descent parsers for Liberty and LEF, because both formats are bracket/block data formats rather than general programming languages.
- `ruff`, `mypy --strict`, and `pytest` in CI.

## Document model

`ParsedDocument` is the top-level parser return type. It stores a human-readable summary, format metadata, semantic chunks, and the raw AST. `Chunk` is the retrieval unit. The LangChain conversion keeps document metadata under `doc_*` keys so chunk-level metadata can retain native names without collisions.

## Current parser status

- Liberty parses real ASAP7 and SKY130 Liberty fixtures.
- LEF parses real SKY130 tech and merged LEF fixtures.
- SDC and SPEF fixtures are present for future work, but parsers are not implemented yet.
