# S6: synthesise the FIFO RTL to the SKY130 hd standard cells (one liberty corner).
# Run by verify/sta.py inside a no-network container: yosys -c synth.tcl
# Inputs (read-only): /work/in/dut.v (RTL), $::env(LIB) (liberty),
# /work/pdkcfg/{no_synth,drc_exclude}.cells (the PDK's cells not to synthesise with,
# the same lists the OpenLane flow uses).
yosys -import
set lib $::env(LIB)

set dont_use {}
foreach f {/work/pdkcfg/no_synth.cells /work/pdkcfg/drc_exclude.cells} {
    set fh [open $f r]
    foreach line [split [read $fh] "\n"] {
        set c [string trim $line]
        if {$c ne "" && [string index $c 0] ne "#"} { lappend dont_use -dont_use $c }
    }
    close $fh
}

read_liberty -lib $lib
read_verilog -defer /work/in/dut.v
hierarchy -check -top sync_fifo
synth -top sync_fifo -flatten
# flip-flops, then combinational logic, mapped onto liberty cells
dfflibmap -liberty $lib {*}$dont_use
abc -liberty $lib {*}$dont_use
opt_clean -purge
setundef -zero
hilomap -singleton -hicell sky130_fd_sc_hd__conb_1 HI -locell sky130_fd_sc_hd__conb_1 LO
splitnets
opt_clean -purge
check -assert
tee -o /work/out/stat.txt stat -liberty $lib
tee -q -o /work/out/stat.json stat -json -liberty $lib
write_verilog -noattr -noexpr -nohex -nodec /work/out/netlist.v
