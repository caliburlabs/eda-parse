# Liberty

Liberty (`.lib`) files characterize standard-cell libraries for timing, power, and synthesis flows.

## What We Parse

- Top-level `library` group metadata.
- Simple attributes such as units, delay model, nominal process, voltage, and temperature.
- Complex single-argument attributes such as `technology(cmos)`.
- `operating_conditions` groups.
- `cell` groups.
- Per-cell area, leakage power, pin count, power/ground pin count, pin directions, and pin functions.

## Output Shape

- `ParsedDocument.source_format`: `liberty`
- One chunk per `cell`
- Chunk metadata includes `cell_name`, `pin_count`, `pg_pin_count`, `pin_directions`, `functions`, and available scalar attributes.

## Current Fixtures

- `asap7_small_ff.lib.gz`
- `asap7_small_ss.lib.gz`
- `sky130hd_tt.lib.gz`

## Known Limitations

- The parser is read-only and does not currently serialize Liberty back to source.
- Timing table contents are retained in the raw AST but not summarized into chunk metadata yet.
- Bus pin handling is basic.
- Validation currently uses redistributable public fixtures, not committed CMC-restricted PDK files.
