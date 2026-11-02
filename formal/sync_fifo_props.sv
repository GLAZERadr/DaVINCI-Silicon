// sync_fifo_props.sv - frozen formal properties for sync_fifo (hand-written).
// Pinned in formal/props.sha256. Never shown to or written by the model.
//
// Uses only the ports from spec/interface.json, so it checks any RTL with the
// right interface whatever it names its internals. Parameters are the
// defaults the frozen testbench uses (WIDTH 8, DEPTH 16, AF_THRESH 14).
// Inputs are free; the only assumption is reset in the first cycle.
// Each property can be enabled on its own (EN bit) so every one gets its own
// result: P1 count_le_depth, P2 full_iff_count, P3 empty_iff_count,
// P4 never_full_and_empty, P5 overflow_cause, P6 count_step.
module fifo_formal #(
    parameter [5:0] EN = 6'b111111
) (
    input wire       clk,
    input wire       rst,
    input wire       wr_en,
    input wire [7:0] din,
    input wire       rd_en
);
    localparam DEPTH = 16;

    wire [7:0] dout;
    wire       full, empty, almost_full, overflow, underflow;
    wire [4:0] count;

    sync_fifo dut (
        .clk(clk), .rst(rst), .wr_en(wr_en), .din(din), .rd_en(rd_en),
        .dout(dout), .full(full), .empty(empty), .almost_full(almost_full),
        .overflow(overflow), .underflow(underflow), .count(count)
    );

    // Observer state: our own registers, not the design's.
    reg       init = 1'b1;        // first cycle: reset assumed, nothing checked
    reg       prev_rst;
    reg       prev_ovf_cause;     // last cycle: write while full, no read, no reset
    reg [4:0] prev_count;
    always @(posedge clk) begin
        init           <= 1'b0;
        prev_rst       <= rst;
        prev_ovf_cause <= !rst && wr_en && full && !rd_en;
        prev_count     <= count;
    end

    always @* if (init) assume (rst);

    always @* if (!init) begin
        if (EN[0]) P1_count_le_depth:       assert (count <= DEPTH);
        if (EN[1]) P2_full_iff_count:       assert (full == (count == DEPTH));
        if (EN[2]) P3_empty_iff_count:      assert (empty == (count == 0));
        if (EN[3]) P4_never_full_and_empty: assert (!(full && empty));
        if (EN[4]) P5_overflow_cause:       assert (!overflow || prev_ovf_cause);
        // 6-bit compare so a wrap (0 -> 31) counts as a jump, not a step.
        if (EN[5] && !prev_rst) P6_count_step:
            assert ({1'b0, count} == {1'b0, prev_count}
                 || {1'b0, count} == {1'b0, prev_count} + 6'd1
                 || {1'b0, count} + 6'd1 == {1'b0, prev_count});
    end
endmodule
