// rr_arbiter: 4-requester round-robin arbiter, registered one-hot grant,
// synchronous active-high reset. Hand-written reference RTL for
// blocks/rr_arbiter (spec: blocks/rr_arbiter/spec.md).
module rr_arbiter (
    input  wire       clk,
    input  wire       rst,
    input  wire [3:0] req,
    output reg  [3:0] grant
);
    reg [1:0] ptr;    // requester with the highest priority at the next edge
    reg [1:0] pick;   // first requester at or after ptr, rotating
    reg [1:0] idx;
    reg       found;
    integer   k;

    always @(*) begin
        found = 1'b0;
        pick  = ptr;
        for (k = 0; k < 4; k = k + 1) begin
            idx = ptr + k[1:0];
            if (!found && req[idx]) begin
                found = 1'b1;
                pick  = idx;
            end
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            grant <= 4'b0000;
            ptr   <= 2'd0;
        end else if (found) begin
            grant <= 4'b0001 << pick;
            ptr   <= pick + 2'd1;
        end else begin
            grant <= 4'b0000;
        end
    end
endmodule
