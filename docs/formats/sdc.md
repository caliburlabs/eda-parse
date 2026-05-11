# SDC (Synopsys Design Constraints)

SDC is a TCL-derived constraint format used by every digital synthesis, placement, and timing tool to express design intent (clock periods, I/O delays, false/multicycle paths, clock groupings). Spec: Synopsys SDC reference.

## What We Parse

Recognized constraint commands, each emitting one chunk:

- `create_clock` (chunk kind: `clock`) — extracts `period`, `name`, `waveform`, `ports`.
- `create_generated_clock` (kind: `generated_clock`) — extracts `name`, `source`, `divide_by`, `multiply_by`, `master_clock`.
- `set_input_delay` (kind: `input_delay`) — extracts `delay`, `clock`, `ports`, plus `min`/`max`/`clock_fall` booleans.
- `set_output_delay` (kind: `output_delay`) — same shape as `set_input_delay`.
- `set_input_transition` (kind: `input_transition`) — extracts `transition`, `ports`.
- `set_load` (kind: `load`) — extracts `load`, `ports`.
- `set_false_path` (kind: `false_path`) — extracts `from`, `to`, `through`.
- `set_multicycle_path` (kind: `multicycle_path`) — extracts `cycles`, `from`, `to`, `through`, plus `setup`/`hold`/`start`/`end` booleans.
- `set_clock_groups` (kind: `clock_groups`) — extracts `groups` (list of brace-list contents), plus `asynchronous`/`physically_exclusive`/`logically_exclusive` booleans.

Plus side-effect commands that update document-level metadata without emitting a chunk:

- `set <var> <value>` — tracked in `metadata["variables"]`; `$var` references in later commands are resolved inline at parse time.
- `current_design <name>` — recorded in `metadata["design"]`.

## TCL semantics handled

- `#`-line comments
- `\`-newline continuation (statement folds across source lines)
- Newline and `;` as statement terminators
- Double-quoted strings with `\`-newline continuation
- Brace-lists `{a b c}` — content captured as a space-joined string (treated as literal TCL, no command-substitution inside)
- Bracket command-substitution `[get_ports clk]` — captured verbatim as the textual command string, with the bracket pair preserved
- `$var` references resolved at parse time when the variable was previously `set`. Unresolved references (e.g. `$x` with no prior `set x ...`) are left as-is.

## Output Shape

- `ParsedDocument.source_format`: `sdc`
- One chunk per recognized constraint statement
- `ParsedDocument.metadata` includes per-kind counts (`clock_count`, `input_delay_count`, `output_delay_count`, `false_path_count`, `multicycle_path_count`, `clock_groups_count`, …) plus `variables` and `design`.

## Current Fixtures

- `gcd_sky130hd.sdc` (1 clock, 1 input_delay, 1 output_delay, 1 input_transition, plus 3 `set` assignments)

## Known Limitations

- Bracket expressions are *not* evaluated. `[expr $period * 0.2]` is stored as a string. Downstream consumers can evaluate or ignore.
- TCL flow control (`if`, `for`, `foreach`, `proc`) is not recognized. Real-world SDCs sometimes use these for parametric constraints; we treat the body tokens as a single statement and may produce odd output if encountered. Issue welcome with a fixture.
- Brace-list contents are joined with single spaces; the original source whitespace inside `{...}` is not preserved exactly.
- `set_disable_timing`, `set_case_analysis`, `set_max_delay`/`set_min_delay`, and other less-common constraints are recognized as statements but do not emit chunks yet. Adding them is a small extension to `_chunk_for`.
