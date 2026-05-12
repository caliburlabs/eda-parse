# Provenance — authority_001_ol_1371_hold_repair_setup_conflict

This file is the audit trail for the sealed answer in `golden.json`. It is
the chamber-busting evidence: the diagnosis here was written by named
external chip-design maintainers, in a public thread, before this
benchmark existed and without anyone in the bench-building loop being a
party to it.

## Source

GitHub issue: https://github.com/The-OpenROAD-Project/OpenLane/issues/1371
Filed: 2022-09 (sky130hd, OpenLane, ycr4_iconnect design).

## Verbatim maintainer diagnoses

> **jjcherry56** (James Cherry — OpenSTA author, Parallax Software):
>
> "fixed in openroad 79313e90d"
>
> "Setup repair splits non-violating loads from violating loads and hold
> repair could do the same."

> **antonblanchard** (Anton Blanchard — IBM / Linux kernel maintainer):
>
> "The resizer is unable to resolve all the setup violations, and hold
> fixup is being told not to create setup violations and so can't make
> progress. Increasing the clock period from 10 to 16 so setup repair can
> pass fixes the issue."

## What actually closed it

- **Fix commit:** `openroad 79313e90d` (named in-thread by Cherry).
- **Fix file:** `src/rsz/src/RepairHold.cc` (refactor of the gating
  condition so `allow_setup_violations` is the outer guard rather than
  nested inside the setup-margin check).
- **User-level workaround at the OpenLane env layer:** flip
  `GLB_RESIZER_ALLOW_SETUP_VIOS` from `0` to `1`. The reproducer's
  `run.sh` line 35 and `run.tcl` line 33 set this to `0`, which is what
  triggered the failure path; the OpenLane resizer script
  `resizer_routing_timing.tcl` lines 71–72 show the conditional that
  appends `-allow_setup_violations` to the OpenROAD invocation when this
  env var is set.

## Why the agent should be able to find this

The reproducer leaves a clear trail:

1. `16-resizer.log` shows `RSZ-0062 Unable to repair all setup
   violations` immediately followed by `RSZ-0046 Found 5 endpoints with
   hold violations` and then `RSZ-0064 Unable to repair all hold checks
   within margin`. The ordering is the diagnosis: setup repair fails
   first, hold repair then can't make progress.
2. `reproducer/run.sh:35` and `reproducer/run.tcl:33` both set
   `GLB_RESIZER_ALLOW_SETUP_VIOS='0'`.
3. `reproducer/openlane/scripts/openroad/resizer_routing_timing.tcl:71-72`
   shows the OpenLane script gating the OpenROAD `-allow_setup_violations`
   flag on that env var.

An agent that reads the log, greps for the env var, and connects the two
should converge on the same diagnosis the maintainers gave.

## Schema translation

The grader uses the format in `golden.json` (`required_exact`,
`required_numeric`, `required_evidence`, `required_next_action_terms`).
This document holds the rich provenance metadata that the grader does
not score against but that an audit can use to verify the case is real.

## Attribution

If/when the bench publishes, this case requires attribution to:

- James Cherry (jjcherry56 — also posts as parallaxsw)
- Anton Blanchard (antonblanchard)
- Mohamed Gaber (donn — OpenLane lead)

A NOTICE file collecting attributions across all authority cases is the
publish-day obligation.
