create_clock -name core_clk -period 2.0 [get_ports clk_core]
set_input_delay 0.20 -clock core_clk [get_ports a]
set_output_delay 0.20 -clock core_clk [get_ports y]

