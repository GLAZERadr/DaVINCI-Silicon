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

    function [31:0] clog2;
        input [31:0] v;
        reg [31:0] tmp;
        integer i;
        begin
            tmp = v - 1'b1;
            clog2 = 32'd0;
            for (i = 0; i < 32; i = i + 1) begin
                if (tmp > 32'd0) begin
                    tmp = tmp >> 1;
                    clog2 = clog2 + 32'd1;
                end
            end
            if (clog2 == 32'd0) begin
                clog2 = 32'd1;
            end
        end
    endfunction

    localparam PTRW = clog2(DEPTH);

    reg [WIDTH-1:0] mem [0:DEPTH-1];
    reg [PTRW-1:0] wr_ptr;
    reg [PTRW-1:0] rd_ptr;

    wire do_read;
    wire do_write;

    assign full = (count == DEPTH);
    assign empty = (count == 0);
    assign almost_full = (count >= AF_THRESH);

    assign do_read = rd_en && !empty;
    assign do_write = wr_en && (!full || rd_en);

    always @(posedge clk) begin
        if (rst) begin
            count <= {CW{1'b0}};
            dout <= {WIDTH{1'b0}};
            overflow <= 1'b0;
            underflow <= 1'b0;
            wr_ptr <= {PTRW{1'b0}};
            rd_ptr <= {PTRW{1'b0}};
        end else begin
            overflow <= wr_en && full && !rd_en;
            underflow <= rd_en && empty;
            if (do_write) begin
                mem[wr_ptr] <= din;
                if (wr_ptr == (DEPTH - 1))
                    wr_ptr <= {PTRW{1'b0}};
                else
                    wr_ptr <= wr_ptr + 1'b1;
            end
            if (do_read) begin
                dout <= mem[rd_ptr];
                if (rd_ptr == (DEPTH - 1))
                    rd_ptr <= {PTRW{1'b0}};
                else
                    rd_ptr <= rd_ptr + 1'b1;
            end
            if (do_write && !do_read)
                count <= count + 1'b1;
            else if (do_read && !do_write)
                count <= count - 1'b1;
            else
                count <= count;
        end
    end

endmodule
```