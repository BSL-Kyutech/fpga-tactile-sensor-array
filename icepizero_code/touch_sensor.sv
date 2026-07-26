// Self-capacitance touch sensor for iCEpi Zero
// Resistor wiring: 1MΩ between 3.3V and touch_pad pin
// Touch pad (copper area) also connected to same pin
//
// How it works:
//   DISCHARGE phase: drive pin LOW to drain all charge
//   CHARGE   phase: release to High-Z, count cycles until pin reads HIGH
//   With finger present, capacitance increases -> takes longer to charge -> higher count
//
// At 50MHz:
//   DISCHARGE_CYCLES = 2500  -> 50µs discharge (enough for 1MΩ RC)
//   MAX_COUNT        = 65000 -> ~1.3ms max charge wait
//   TOUCH_THRESHOLD  = 500   -> tune this after seeing your baseline

module touch_sensor #(
    parameter CLK_FREQ        = 50_000_000,
    parameter DISCHARGE_CYCLES = 2500,       // 50µs at 50MHz — fully drains pad
    parameter TOUCH_THRESHOLD  = 100,        // start here; lower = more sensitive
    parameter MAX_COUNT        = 16'd2500   // safety ceiling
) (
    input  logic clk,
    inout  logic touch_pad,
    output logic [15:0] measurement,         // raw count — watch this to tune threshold
    output logic        touch_detected,
    output logic        measurement_ready    // 1-cycle pulse when new reading is done
);

    logic [15:0] timer         = 0;
    logic [15:0] discharge_cnt = 0;
    logic [1:0]  state         = 0;  // 0=discharge, 1=charge, 2=done
    logic        pad_oe        = 1;
    logic        pad_out       = 0;

    // Tristate driver: drive LOW during discharge, High-Z during charge
    assign touch_pad = pad_oe ? pad_out : 1'bz;

    // Outputs
    assign measurement    = timer;
    assign touch_detected = (timer > TOUCH_THRESHOLD);

    always @(posedge clk) begin
        measurement_ready <= 1'b0;  // default: no pulse

        case (state)

            // ── DISCHARGE ──────────────────────────────────────────────
            2'd0: begin
                pad_oe  <= 1'b1;
                pad_out <= 1'b0;

                if (discharge_cnt >= DISCHARGE_CYCLES - 1) begin
                    discharge_cnt <= 0;
                    timer         <= 0;
                    pad_oe        <= 1'b0;  // release to High-Z NOW
                    state         <= 2'd1;
                end else begin
                    discharge_cnt <= discharge_cnt + 1;
                end
            end

            // ── CHARGE / COUNT ─────────────────────────────────────────
            2'd1: begin
                pad_oe <= 1'b0;  // keep High-Z

                if (touch_pad == 1'b1 || timer >= MAX_COUNT) begin
                    measurement_ready <= 1'b1;  // pulse: reading is valid
                    state             <= 2'd0;  // go back to discharge
                end else begin
                    timer <= timer + 1;
                end
            end

            default: state <= 2'd0;

        endcase
    end

endmodule
