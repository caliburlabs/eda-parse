module timing_seed_overconstrained_clock (
    input wire clk,
    input wire rst_n,
    input wire [7:0] a,
    output reg [7:0] y
);
    reg [7:0] stage;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage <= 8'h00;
            y <= 8'h00;
        end else begin
            stage <= (a << 1) ^ (a + 8'h3d);
            y <= {stage[6:0], stage[7]} + 8'h11;
        end
    end
endmodule

