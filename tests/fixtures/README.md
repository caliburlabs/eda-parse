# Test fixtures

All files here are committed under their **upstream licenses** (BSD-3 / Apache 2.0). Each is real industrial PDK output, not synthetic, and was fetched from a public upstream that already redistributes it.

## Liberty (`liberty/`)

| File | Cells | Source | License | Notes |
|------|-------|--------|---------|-------|
| `asap7_small_ff.lib.gz` | 3 | ASU ASAP7 (via OpenSTA) | BSD-3-Clause | 7nm FinFET predictive PDK, fast-fast corner. Smallest fixture and primary unit test target. |
| `asap7_small_ss.lib.gz` | 3 | ASU ASAP7 (via OpenSTA) | BSD-3-Clause | Slow-slow corner of the same library. |
| `sky130hd_tt.lib.gz` | ~430 | Google/SkyWater SKY130 PDK (via OpenSTA) | Apache 2.0 | Real industrial 130nm CMOS, high-density library, TT 25 C 1.8 V corner. |

## LEF (`lef/`)

| File | Kind | Source | License |
|------|------|--------|---------|
| `sky130_fd_sc_hd.tlef` | Technology LEF | Google/SkyWater (via OpenROAD-flow-scripts) | Apache 2.0 |
| `sky130_fd_sc_hd_merged.lef` | Merged cell LEF (441 macros) | Google/SkyWater (via OpenROAD-flow-scripts) | Apache 2.0 |

## SDC (`sdc/`)

| File | Source | License |
|------|--------|---------|
| `gcd_sky130hd.sdc` | OpenSTA examples (Synopsys Design Constraints for a synthesized GCD) | BSD-3-Clause |

## SPEF (`spef/`)

| File | Source | License |
|------|--------|---------|
| `gcd_sky130hd.spef` | OpenSTA examples (post-layout parasitics for GCD on SKY130) | BSD-3-Clause |

## What we do NOT ship

TSMC 65/130/180, Cadence GPDK 045/090/180, cmosp18, AMF/SiEPIC photonics, MUMPs MEMS, and any other CMC-restricted kit. Those can be validated against in a private environment, but only summary stats such as cell counts, macro counts, parse times, and pass/fail status should ever be recorded in this repo.

## Adding a new fixture

1. Confirm the file is redistributable under its upstream license.
2. Drop it under the appropriate subdirectory.
3. Add a row to the relevant table above with source + license.
4. If gzipped, the parser should open `.gz` transparently, with no decompression at commit time.
