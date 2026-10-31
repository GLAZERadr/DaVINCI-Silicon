# sync_fifo — interface

Port names, widths and parameters are fixed by the test bench. Behaviour is given by the approved requirements.

## Parameters

| Name | Default | Meaning |
| --- | --- | --- |
| `WIDTH` | 8 | data width in bits |
| `DEPTH` | 16 | number of entries |
| `AF_THRESH` | 14 | `almost_full` threshold |
| `CW` | 5 | width of `count`; must hold 0..DEPTH |

## Interface

```verilog
module sync_fifo #(
    parameter WIDTH     = 8,
    parameter DEPTH     = 16,
    parameter AF_THRESH = 14,
    parameter CW        = 5
) (
    input  wire             clk,
    input  wire             rst,          // synchronous, active high
    input  wire             wr_en,
    input  wire [WIDTH-1:0] din,
    input  wire             rd_en,
    output reg  [WIDTH-1:0] dout,         // registered read data
    output wire             full,
    output wire             empty,
    output wire             almost_full,
    output reg              overflow,     // one-cycle pulse
    output reg              underflow,    // one-cycle pulse
    output reg  [CW-1:0]    count
);
```

Port names, widths and directions are fixed. Outputs may be `reg` or `wire`
as long as the approved behaviour holds.

## Constraints on generated RTL

- Synthesisable Verilog-2001, one module named `sync_fifo`.
- No `$system`, `$fopen`/file I/O, `$readmem*`, `$finish`/`$stop`, `$dump*` or `` `include ``. The pipeline rejects RTL that contains them.
