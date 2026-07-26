// High-speed Capacitance Sensor - 1.5 kHz data streaming for 98 sensors
module top (
    input clk,
    inout [1:0] sense_pins,
    output [1:0] leds,
    output uart_tx
);
    parameter NUM_SENSORS = 2;
    parameter TOUCH_THRESHOLD = 14'd10;
    parameter MAX_CHARGE_COUNT = 14'd5000;
    parameter DISCHARGE_CYCLES = 12;

    // SB_IO for each sense pin with pullup
    wire [NUM_SENSORS-1:0] pad_ins;
    reg [NUM_SENSORS-1:0] pad_oes = 0; // Default tristate
    reg [NUM_SENSORS-1:0] pad_outs = 0; // Always 0

    genvar j;
    generate
        for (j = 0; j < NUM_SENSORS; j = j + 1) begin : sb_io_inst
            SB_IO #(
                .PIN_TYPE(6'b101001),
                .PULLUP(1'b1)
            ) sb_io (
                .PACKAGE_PIN(sense_pins[j]),
                .OUTPUT_ENABLE(pad_oes[j]),
                .D_OUT_0(pad_outs[j]),
                .D_IN_0(pad_ins[j])
            );
        end
    endgenerate

    // Measurements and touch detection
    reg [13:0] measurements [0:NUM_SENSORS-1];
    reg [NUM_SENSORS-1:0] touch_detecteds = 0;
    reg [NUM_SENSORS-1:0] touch_detected_prevs = 0;
    wire [NUM_SENSORS-1:0] touch_events;
    assign touch_events = touch_detecteds & ~touch_detected_prevs;
    wire any_touch_event = |touch_events;

    localparam STATE_DISCHARGE = 0;
    localparam STATE_CHARGE = 1;
    reg [0:0] state = STATE_DISCHARGE;
    reg [13:0] timer_counter = 0;
    reg [4:0] discharge_cnt = 0;
    reg [NUM_SENSORS-1:0] done = 0;

    integer k;
    reg [NUM_SENSORS-1:0] next_done;  // Temporary for next state (Verilog-compatible)

    always @(posedge clk) begin
        touch_detected_prevs <= touch_detecteds;

        case (state)
            STATE_DISCHARGE: begin
                pad_oes <= {NUM_SENSORS{1'b1}}; // Ground all pads
                discharge_cnt <= discharge_cnt + 1;
                if (discharge_cnt >= DISCHARGE_CYCLES - 1) begin
                    state <= STATE_CHARGE;
                    discharge_cnt <= 0;
                    timer_counter <= 0;
                    done <= 0;
                end
            end
            STATE_CHARGE: begin
                pad_oes <= {NUM_SENSORS{1'b0}}; // Tristate all, charge via pullups
                timer_counter <= timer_counter + 1;
                next_done = done;  // Start with current done
                for (k = 0; k < NUM_SENSORS; k = k + 1) begin
                    if (!done[k] && pad_ins[k]) begin
                        measurements[k] <= timer_counter;
                        touch_detecteds[k] <= (timer_counter > TOUCH_THRESHOLD);
                        next_done[k] = 1'b1;  // Update temp (blocking)
                    end
                end
                done <= next_done;  // Apply updates
                if (&next_done || timer_counter >= MAX_CHARGE_COUNT - 1) begin
                    for (k = 0; k < NUM_SENSORS; k = k + 1) begin
                        if (!next_done[k]) begin
                            measurements[k] <= MAX_CHARGE_COUNT;
                            touch_detecteds[k] <= (MAX_CHARGE_COUNT > TOUCH_THRESHOLD);
                        end
                    end
                    state <= STATE_DISCHARGE;
                end
            end
        endcase
    end

    // --- LED INDICATORS (using sensor 0) ---
    reg [23:0] blink_counter = 0;
    wire blink_on;
    always @(posedge clk) blink_counter <= blink_counter + 1;
    assign blink_on = blink_counter[22];
    assign leds[1] = touch_detecteds[0] & blink_on;
    // assign leds[6:1] = measurements[0][5:0]; // Commented: Needs more LEDs defined in pins.pcf
    assign leds[0] = touch_detecteds[0];

    // --- 1.5 kHz UART STREAMING for all sensors ---
    reg [7:0] uart_data_to_send = 0;
    reg uart_send_trigger = 0;
    wire uart_busy;

    reg [7:0] send_index = 0;
    reg sending_block = 0;

    // 666us timer = 8,000 cycles @ 12MHz for 1.5 kHz
    reg [12:0] transmit_timer = 0;

    always @(posedge clk) begin
        transmit_timer <= transmit_timer + 1;
        uart_send_trigger <= 0;

        if (sending_block) begin
            if (!uart_busy && !uart_send_trigger) begin
                if (send_index < NUM_SENSORS + 1) begin
                    if (send_index == 0) begin
                        uart_data_to_send <= 8'd254;
                    end else begin
                        uart_data_to_send <= measurements[send_index - 1][7:0]; // Send lower 8 bits
                    end
                    uart_send_trigger <= 1'b1;
                    send_index <= send_index + 1;
                end else begin
                    sending_block <= 0;
                end
            end
        end

        if ((transmit_timer >= 13'd2999 || any_touch_event) && !sending_block && !uart_busy) begin
            transmit_timer <= 0;
            sending_block <= 1'b1;
            send_index <= 0;
        end
    end

    // --- 2000000 BAUD UART ---
    uart_tx #(.CLK_FREQ(12_000_000), .BAUD_RATE(2000000)) uart_inst (
        .clk(clk),
        .data(uart_data_to_send),
        .send_pulse(uart_send_trigger),
        .tx(uart_tx),
        .busy(uart_busy)
    );
endmodule
