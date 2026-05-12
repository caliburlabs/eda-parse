create_clock -name core_clk -period 5.0 [get_ports clk]
set_output_delay 0.50 -clock core_clk [get_ports data_out[*]]
set_input_transition 0.05 [all_inputs]
set_load 0.01 [all_outputs]

