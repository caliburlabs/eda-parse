# Archived public issue excerpt - OpenROAD #4833

Issue title: `Speed up global route, antenna repair in particular`

## Original framing

`oharboe`:

> Then antenna repair takes another 2 hours or so:
>
> ```
> check_antennas
> [WARNING GRT-0246] No diode with LEF class CORE ANTENNACELL found.
> [INFO ANT-0002] Found 0 net violations.
> [INFO ANT-0001] Found 0 pin violations.
> Warning: There are 3785 unconstrained endpoints.
> [2 hours before completion]
> ```
>
> I'm aware of SKIP_ANTENNA_REPAIR and SKIP_REPORT_METRICS variables, but of
> course it would be simpler if antenna repair wasn't so slow that I would have
> to worry about it.

## Maintainer rerun and correction

`eder-matheus`:

> @oharboe We recently added parallelization to check_antennas and
> repair_antennas. After the PR
> https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/pull/2063, it
> will be on by default in ORFS. I will try with the provided test case.

`eder-matheus`:

> @oharboe As a follow-up on the tests with parallelization, I see that the GRT
> + the incremental flow runtime is about 53 minutes. The repair_antennas +
> check_antennas ends in ~4 minutes, using 16 threads. The remaining runtime is
> spent in estimate_parasitics. I started another run to get the exact value for
> the estimate_parasitics runtime. I will study if it's possible to speed up this
> step with parallelization or other optimization.

`eder-matheus`:

> @oharboe I found the problem lies in report_metrics, not estimate_parasitics. I
> didn't notice it when editing the script to get the runtimes, but now I see this:
> * 54 minutes in GRT + incremental
> * 4 minutes in repair_antennas + check_antennas
> * 2.5 minutes in estimate_parasitics
>
> The remaining runtime is only with report_metrics, which is about 2 hours.
