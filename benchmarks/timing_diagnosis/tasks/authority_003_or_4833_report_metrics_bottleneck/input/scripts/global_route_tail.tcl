puts "\n=========================================================================="
puts "check_antennas"
puts "--------------------------------------------------------------------------"

if {![info exist env(SKIP_ANTENNA_REPAIR)]} {
  repair_antennas -iterations 5
  check_placement -verbose
  check_antennas -report_file $env(REPORTS_DIR)/antenna.log
}

estimate_parasitics -global_routing
report_metrics 5 "global route"

# Write SDC to results with updated clock periods that are just failing.
# Use make target update_sdc_clock to install the updated sdc.
source [file join $env(SCRIPTS_DIR) "write_ref_sdc.tcl"]

write_db $env(RESULTS_DIR)/5_1_grt.odb
