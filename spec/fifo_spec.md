# sync_fifo — specification

Single-clock synchronous FIFO. This is the spec the model receives; the frozen
suite in `tests/` and the golden model `tests/golden_model.py` are the
executable form of the same rules. Requirements REQ-01..10 are listed in
`spec/requirements.json` with the tests that cover each one.

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
as long as the timing below holds.

## Timing

Everything changes on the rising edge of `clk`. Inputs are sampled at that
edge; the outputs below describe their value just after it.

Let `full`, `empty` and `count` be the values *before* the edge.

- `do_read  = rd_en && !empty`
- `do_write = wr_en && (!full || rd_en)` — a write while full succeeds only if a read happens in the same cycle.

On the edge:

1. **Reset (REQ-01).** If `rst` is 1: the FIFO becomes empty, `count = 0`, `dout = 0`, `overflow = 0`, `underflow = 0`. Nothing else happens.
2. **Flags.** `overflow <= wr_en && full && !rd_en` (REQ-04); a write while full with a same-cycle read does not raise it (REQ-10). `underflow <= rd_en && empty` (REQ-05, REQ-07). Both are set for exactly one cycle per offending request.
3. **Read.** If `do_read`, `dout` takes the oldest stored word and that word is removed. Otherwise `dout` holds its previous value (REQ-05).
4. **Write.** If `do_write`, `din` is stored as the newest word.
5. **Count (REQ-09).** `count` increases by 1 on write-only, decreases by 1 on read-only, and is unchanged when both or neither happen.

Combinational status, from the current `count`:

- `full  = (count == DEPTH)`, `empty = (count == 0)` (REQ-03)
- `almost_full = (count >= AF_THRESH)` (REQ-08)

## Ordering

Words leave in the order they arrived, including across pointer wraparound
(REQ-02). When full, a same-cycle read and write returns the oldest word and
stores the new one; `count` stays `DEPTH` (REQ-06). When empty, a same-cycle
read and write stores the word, the read is ignored and `underflow` pulses
(REQ-07).

## Constraints on generated RTL

- Synthesisable Verilog-2001, one module named `sync_fifo`.
- No `$system`, `$fopen`/file I/O, `$readmem*`, `$finish`/`$stop`, `$dump*` or `` `include ``. The pipeline rejects RTL that contains them.
