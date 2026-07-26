module top (
    input         clk,
    input         usb_rx,
    output        usb_tx,
    output [4:0]  led,
    inout  [19:0] touch_pad,   // Sensors 0-19, all GPIO + tp[0]
    // SPI Slave
    input  pi_sclk,
    input  pi_mosi,
    output pi_miso,
    input  pi_ce0,
    output pi_nirq
);
    assign usb_tx = usb_rx;

    // ─── 20 Touch Sensors ─────────────────────────────────────────────
    logic [15:0] touch_value [0:19];
    logic [19:0] touch_det;
    logic [19:0] meas_ready;

    genvar i;
    generate
        for (i = 0; i < 20; i++) begin : TOUCH_GEN
            touch_sensor #(
                .CLK_FREQ         (50_000_000),
                .DISCHARGE_CYCLES (2500),
                .TOUCH_THRESHOLD  (100),
                .MAX_COUNT        (16'd2000)
            ) u_touch (
                .clk               (clk),
                .touch_pad         (touch_pad[i]),
                .measurement       (touch_value[i]),
                .touch_detected    (touch_det[i]),
                .measurement_ready (meas_ready[i])
            );
        end
    endgenerate

    // ─── Latch latest values ──────────────────────────────────────────
    logic [15:0] latched_val [0:19];
    logic [19:0] latched_det = '0;

    always_ff @(posedge clk) begin
        for (int j = 0; j < 20; j++) begin
            if (meas_ready[j]) begin
                latched_val[j] <= touch_value[j];
                latched_det[j] <= touch_det[j];
            end
        end
    end

    // ─── SPI Packet ───────────────────────────────────────────────────
    // 62 bytes:
    //   [0]       = 0xAB  sync
    //   [3*i+1]   = {7'b0, touch_detected[i]}   i = 0..19
    //   [3*i+2]   = value[i][15:8]
    //   [3*i+3]   = value[i][7:0]
    //   [61]      = 0xFF  end marker
    localparam int PKT_LEN = 62;
    logic [7:0] pkt [0:PKT_LEN-1];

    always_ff @(posedge clk) begin
        pkt[0] <= 8'hAB;
        for (int j = 0; j < 20; j++) begin
            pkt[3*j+1] <= {7'b0, latched_det[j]};
            pkt[3*j+2] <= latched_val[j][15:8];
            pkt[3*j+3] <= latched_val[j][7:0];
        end
        pkt[61] <= 8'hFF;
    end

    // ─── SPI Slave ────────────────────────────────────────────────────
    reg [2:0] sclk_sync = '0;
    reg [2:0] ce0_sync  = '0;
    always_ff @(posedge clk) begin
        sclk_sync <= {sclk_sync[1:0], pi_sclk};
        ce0_sync  <= {ce0_sync[1:0],  pi_ce0};
    end

    wire sclk_falling = (sclk_sync[2:1] == 2'b10);
    wire cs_active    = (ce0_sync[1] == 1'b0);

    // byte_idx needs to reach 61 → 6 bits
    reg [2:0] bit_cnt  = '0;
    reg [5:0] byte_idx = '0;
    reg [7:0] shift_reg = '0;
    reg       cs_prev   = 1'b1;

    always_ff @(posedge clk) begin
        cs_prev <= ce0_sync[1];

        // CS falling edge → reset and load first byte
        if (cs_prev == 1'b1 && ce0_sync[1] == 1'b0) begin
            shift_reg <= pkt[0];
            bit_cnt   <= '0;
            byte_idx  <= '0;
        end

        if (cs_active && sclk_falling) begin
            shift_reg <= {shift_reg[6:0], 1'b0};
            bit_cnt   <= bit_cnt + 1'b1;
            if (bit_cnt == 3'd7) begin
                bit_cnt <= '0;
                if (byte_idx < PKT_LEN - 1) begin
                    byte_idx  <= byte_idx + 1'b1;
                    shift_reg <= pkt[byte_idx + 1];
                end else begin
                    byte_idx  <= '0;
                    shift_reg <= pkt[0];
                end
            end
        end
    end

    assign pi_miso = cs_active ? shift_reg[7] : 1'b0;
    assign pi_nirq = ~(|latched_det);   // low when ANY sensor touched

    // ─── LEDs (grouped by sensor range) ───────────────────────────────
    assign led[0] = |latched_det[3:0];    // sensors 0-3
    assign led[1] = |latched_det[7:4];    // sensors 4-7
    assign led[2] = |latched_det[11:8];   // sensors 8-11
    assign led[3] = |latched_det[15:12];  // sensors 12-15
    assign led[4] = |latched_det[19:16];  // sensors 16-19

endmodule
