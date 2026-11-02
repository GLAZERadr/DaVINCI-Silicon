DIAGNOSIS: The prior RTL altered the fixed interface — dropping required vector ranges, adding an extra port, and changing directions — so its port list no longer matched the spec.
```verilog
module sync_fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 16,
    parameter AF_THRESH = 14,
    parameter CW = 5
) (
    input  wire             clk,
    input  wire             rst,
    input  wire             wr_en,
    input  wire [WIDTH-1:0] din,
    input  wire             rd_en,
    output reg  [WIDTH-1:0] dout,
    output wire             full,
    output wire             empty,
    output wire             almost_full,
    output reg              overflow,
    output reg              underflow,
    output reg  [CW-1:0]    count
);

    localparam PTR_W = (DEPTH <= 2) ? 1 :
                       (DEPTH <= 4) ? 2 :
                       (DEPTH <= 8) ? 3 :
                       (DEPTH <= 16) ? 4 :
                       (DEPTH <= 32) ? 5 :
                       (DEPTH <= 64) ? 6 :
                       (DEPTH <= 128) ? 7 :
                       (DEPTH <= 256) ? 8 :
                       (DEPTH <= 512) ? 9 :
                       (DEPTH <= 1024) ? 10 :
                       (DEPTH <= 2048) ? 11 : 12;

    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [PTR_W-1:0] wr_ptr;
    reg [PTR_W-1:0] rd_ptr;

    wire do_read;
    wire do_write;

    assign do_read  = rd_en && !empty;
    assign do_write = wr_en && (!full || rd_en);

    assign full        = (count == DEPTH);
    assign empty       = (count == 0);
    assign almost_full = (count >= AF_THRESH);

    always @(posedge clk) begin
        if (rst) begin
            count     <= 0;
            dout      <= 0;
            overflow  <= 1'b0;
            underflow <= 1'b0;
            wr_ptr    <= 0;
            rd_ptr    <= 0;
        end else begin
            overflow  <= wr_en && full && !rd_en;
            underflow <= rd_en && empty;

            if (do_write) begin
                mem[wr_ptr] <= din;
            end

            if (do_read) begin
                dout <= mem[rd_ptr];
            end

            if (do_write) begin
                if (wr_ptr == DEPTH - 1)
                    wr_ptr <= 0;
                else
                    wr_ptr <= wr_ptr + 1'b1;
            end

            if (do_read) begin
                if (rd_ptr == DEPTH - 1)
                    rd_ptr <= 0;
                else
                    rd_ptr <= rd_ptr + 1'b1;
            end

            if (do_write && !do_read)
                count <= count + 1'b1;
            else if (do_read && !do_write)
                count <= count - 1'b1;
        end
    end

endmodule
```