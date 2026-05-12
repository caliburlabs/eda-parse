read_liberty sky130_fd_sc_hd__tt_025C_1v80.lib
read_lef merged_unpadded.lef
read_verilog Top_cell.v

link_design Top_cell

create_clock [get_ports Clk] -name Clk -period 20

puts "clock_skew"
report_clock_skew
exit
