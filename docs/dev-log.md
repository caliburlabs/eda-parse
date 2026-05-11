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
- SDC parses the `gcd_sky130hd.sdc` fixture (1 clock + 1 input_delay + 1 output_delay + 1 input_transition + 3 `set` assignments).
- SPEF fixture is present for future work; parser not implemented yet.

## v0.2.0 (2026-05-11)

Added:

- **SDC parser.** Hand-rolled TCL-ish tokenizer + statement dispatcher. Tracks `set` assignments and resolves `$var` substitutions inline at parse time so downstream metadata carries final numeric values where possible (`create_clock -period $period` becomes `period: 5.0` when `set period 5` appeared earlier). Recognizes `create_clock`, `create_generated_clock`, `set_input_delay`, `set_output_delay`, `set_input_transition`, `set_load`, `set_false_path`, `set_multicycle_path`, `set_clock_groups`. One chunk per constraint; per-kind counts surfaced as document-level metadata.
- **SDCLoader.** Same shape as `LibertyLoader` / `LEFLoader`.
- **`examples/demo_corpus_qa.py`.** Concrete-question script over the real SKY130 Liberty + LEF + SDC trio. Answers five questions (clocks, cells, macros, PVT corner, cross-document sanity check) using only the structured metadata the parsers emit — no embedding model, no LLM. An optional `--with-rag` flag layers a sentence-transformer + FAISS retriever on top for genuinely open-ended queries.

Notes:

- TCL bracket expressions (`[expr ...]`, `[get_ports clk]`) are captured as text, not evaluated. Documented as a known limitation.
- Brace-list contents are joined with single spaces (we tokenize first, so original whitespace inside `{...}` is lost). Cosmetic; downstream consumers can re-normalize.
- The `gcd` SDC names design-level ports, not library cells — the cross-doc Q5 in the demo correctly reports zero matches and explains why. Future demos with synthesized netlists will give richer cross-doc joins.
