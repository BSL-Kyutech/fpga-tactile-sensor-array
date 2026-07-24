// cap_sensor.v - New module for capacitive sensor logic
module cap_sensor (
    input clk,
    input pad_in,
    output pad_oe,
    output pad_out,
    output reg [13:0] last_measurement,
    output reg touch_detected,
    output touch_event
);
    // --- PARAMETERS ---
    parameter TOUCH_THRESHOLD = 14'd10; // Adjust based on observed baseline
    parameter MAX_CHARGE_COUNT = 14'd16383; // Maximum for 14 bits
    parameter DISCHARGE_CYCLES = 20; // Increased for better discharge
    // --- SENSOR STATE ---
    reg [13:0] timer_counter = 0;
    reg [4:0] discharge_cnt = 0;
    reg pad_state_driver = 0;
    reg touch_detected_prev = 0;
    localparam STATE_DISCHARGE = 0;
    localparam STATE_CHARGE = 1;
    reg [0:0] state = STATE_DISCHARGE;
    // Bidirectional pin control
    assign pad_oe = (pad_state_driver == 1'b0);
    assign pad_out = 1'b0;
    // High-speed measurement loop
    always @(posedge clk) begin
        case (state)
            STATE_DISCHARGE: begin
                pad_state_driver <= 1'b0;
                discharge_cnt <= discharge_cnt + 1;
                if (discharge_cnt >= DISCHARGE_CYCLES - 1) begin
                    state <= STATE_CHARGE;
                    discharge_cnt <= 0;
                end
            end
            STATE_CHARGE: begin
                pad_state_driver <= 1'b1;
                timer_counter <= timer_counter + 1;
                if (pad_in == 1'b1 || timer_counter >= MAX_CHARGE_COUNT) begin
                    last_measurement <= timer_counter;
                    touch_detected <= (timer_counter > TOUCH_THRESHOLD);
                    state <= STATE_DISCHARGE;
                    discharge_cnt <= 0;
                    timer_counter <= 0; // Reset timer_counter
                end
            end
        endcase
    end
    // --- EDGE DETECTION for instant event capture ---
    assign touch_event = touch_detected & ~touch_detected_prev;
    always @(posedge clk) begin
        touch_detected_prev <= touch_detected;
    end
endmodule
