# LEF

LEF (`.lef`, `.tlef`) describes technology layers, sites, vias, and cell or macro abstracts used in physical design flows.

## What We Parse

- Top-level version, bus bit characters, divider character, manufacturing grid, and units.
- Technology blocks: `LAYER`, `SITE`, `VIA`, and `VIARULE`.
- Cell macro blocks: `MACRO`, `PIN`, `PORT`, and `OBS`.
- Per-macro class, size, origin, symmetry, site, foreign cell name, pins, and obstruction presence.

## Output Shape

- `ParsedDocument.source_format`: `lef`
- One chunk per `MACRO`
- Tech LEFs produce document metadata and an empty chunk list.
- Cell LEFs produce one macro chunk per `MACRO`.

## Current Fixtures

- `sky130_fd_sc_hd.tlef`
- `sky130_fd_sc_hd_merged.lef`

## Known Limitations

- Geometry is preserved in the raw AST but summarized only lightly.
- Some rarely used LEF extensions may need additional grammar cases.
- DEF parsing is planned separately; LEF and DEF are not handled by the same parser module.
