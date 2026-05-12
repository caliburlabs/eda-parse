create_clock -name core_clk -period 1.0 [get_ports clk]
set_input_delay 0.10 -clock core_clk [get_ports a[*]]
set_output_delay 0.10 -clock core_clk [get_ports y[*]]
set_input_transition 0.05 [all_inputs]
set_load 0.01 [all_outputs]

