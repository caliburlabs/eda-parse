module timing_seed_unconstrained_paths (
    input wire clk,
    input wire rst_n,
    input wire a,
    output reg y
);
    reg q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q <= 1'b0;
            y <= 1'b0;
        end else begin
            q <= a;
            y <= q;
        end
    end
endmodule

