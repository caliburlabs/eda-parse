# Archived public issue excerpt - OpenLane #958

Issue title: `STA hangs at report_clock_skew`

Selected public thread material retained for diagnosis:

## User workaround that surfaced the misleading source comment

`jimbo1990`:

> I fixed temporarily solved this problem as suggested in a previous post by
> commenting out the report_clock_skew from the sta.tcl and also from the
> multiple_cornes.tcl. obviously not ideal however at least the flow finished.
>
> Probably IMPORTANT is that in the SDA.tcl file there is a comment which states
> that the function will hang if a clock less design is detected. What I don't get
> is why it doesn't detect the clock at that point or why it is detecting the
> design as clock less at that point in the synthesis while before it was
> calculating the slack and other parameters fine.

## Maintainer-packaged standalone reproduction

`maliberty`:

> I packaged it myself and have reported it. @donn please address this hole in
> packaging test cases.

Later in the same thread, `maliberty` uploaded `bug.zip`, whose stripped testcase is
represented here by `input/standalone/bug.tcl`.

## External maintainer diagnosis

`jjcherry56`:

> @Manarabdelaty this comment is wrong. report_clock_skew works just find if there
> are no clocks defined.
>
> `# OR hangs if this command is run on clockless designs`
>
> The issue has nothing to do with whether or not clocks are defined. It is a bug
> dealing with combinational feedback loops. OpenSTA has already been fixed but has
> not been integrated into openroad yet because of all the required verification steps.

`jjcherry56`:

> OpenROAD e3315ba41 fixes it on our end
