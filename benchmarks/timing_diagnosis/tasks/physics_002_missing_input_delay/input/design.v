module timing_seed_missing_input_delay (
    input wire clk,
    input wire rst_n,
    input wire [3:0] data_in,
    input wire valid_in,
    output reg [3:0] data_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= 4'h0;
        end else if (valid_in) begin
            data_out <= data_in + 4'h1;
        end
    end
endmodule

