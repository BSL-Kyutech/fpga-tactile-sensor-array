# Makefile for iCE40HX8K Breakout Board
# Usage:
# make -> Build the bitstream
# make prog -> Upload to SRAM (fast, lost on power cycle)
# make flash -> Upload to Flash (permanent)
filename = touch_sensor
pcf_file = pins.pcf
build:
	# 1. Synthesize Verilog to JSON
	yosys -p "synth_ice40 -top top -json $(filename).json" top.v uart_tx.v cap_sensor.v
	# 2. Place and Route (Map to specific FPGA hardware)
	nextpnr-ice40 --hx8k --package ct256 --pcf $(pcf_file) --json $(filename).json --asc $(filename).asc
	# 3. Pack into bitstream
	icepack $(filename).asc $(filename).bin
prog: build
	# Upload to SRAM (requires board connected via USB)
	iceprog -S $(filename).bin
flash: build
	# Upload to Flash
	iceprog $(filename).bin
clean:
	rm -f *.json *.asc *.bin
