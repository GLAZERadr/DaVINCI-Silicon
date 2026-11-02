# S6: pre-layout static timing and power on the synthesised netlist (OpenSTA).
# Ideal clock, no wire parasitics, OpenSTA default switching activity.
# Run by verify/sta.py inside a no-network container.
read_liberty $::env(LIB)
read_verilog /work/out/netlist.v
link_design sync_fifo

set period $::env(PERIOD_NS)
create_clock -name clk -period $period [get_ports clk]
set non_clk [delete_from_list [all_inputs] [get_ports clk]]
set_input_delay 0 -clock clk $non_clk
set_output_delay 0 -clock clk [all_outputs]

puts "DAVINCI period_ns $period"
puts "DAVINCI setup"
report_worst_slack -max -digits 4
puts "DAVINCI hold"
report_worst_slack -min -digits 4
puts "DAVINCI tns"
report_tns -digits 4
puts "DAVINCI end"
report_checks -path_delay max -fields {slew cap input_pins} -digits 4
report_checks -path_delay min -digits 4
report_power -digits 6
