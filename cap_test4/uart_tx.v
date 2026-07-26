// UART Transmitter (2000000 baud, 8N1, 12MHz clock)
module uart_tx (
    input clk,
    input [7:0] data,
    input send_pulse,
    output reg tx,
    output busy
);
    parameter CLK_FREQ = 12_000_000;
    parameter BAUD_RATE = 2000000;
    localparam BIT_PERIOD = CLK_FREQ / BAUD_RATE; // 6 clock cycles per bit
   
    reg [11:0] bit_counter = 0;
    reg [3:0] bit_index = 0;
    reg [8:0] shift_reg = 0;
    reg transmitting = 0;
   
    assign busy = transmitting;
   
    always @(posedge clk) begin
        if (send_pulse && !transmitting) begin
            shift_reg <= {data, 1'b0};
            bit_counter <= 0;
            bit_index <= 0;
            transmitting <= 1'b1;
            tx <= 1'b0;
        end else if (transmitting) begin
            bit_counter <= bit_counter + 1;
            if (bit_counter >= BIT_PERIOD - 1) begin
                bit_counter <= 0;
                bit_index <= bit_index + 1;
               
                if (bit_index < 8) begin
                    tx <= shift_reg[bit_index];
                end else if (bit_index == 8) begin
                    tx <= 1'b1;
                end else begin
                    transmitting <= 1'b0;
                    tx <= 1'b1;
                end
            end
        end else begin
            tx <= 1'b1;
        end
    end
endmodule
