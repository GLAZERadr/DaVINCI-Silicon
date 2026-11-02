# sat_gain — specification

A fixed-point gain stage: a signed Q1.7 sample `x` times a signed Q1.7 gain
`g`, truncated and saturated back to Q1.7, registered. This is the spec the
model receives; the frozen suite in `blocks/sat_gain/tests/` and its
bit-accurate golden model are the executable form of the same rules.
Requirements REQ-01..06 are listed in `blocks/sat_gain/requirements.json`.

## Number format

Q1.7: 8-bit two's complement, value = code / 128. Range -1.0 (`0x80`) to
+127/128 (`0x7f`). No parameters.

## Interface

```verilog
module sat_gain (
    input  wire              clk,
    input  wire              rst,   // synchronous, active high
    input  wire signed [7:0] x,     // Q1.7 sample
    input  wire signed [7:0] g,     // Q1.7 gain
    output reg  signed [7:0] y,     // Q1.7 result, registered
    output reg               sat    // 1 when y was clamped this cycle
);
```

Port names, widths and directions are fixed.

## Behaviour

Everything changes on the rising edge of `clk`; inputs are sampled at that edge.

1. **Reset (REQ-01).** If `rst` is 1: `y = 0`, `sat = 0`.
2. **Product (REQ-03, REQ-06).** `p = x * g` as signed integers, full precision (Q2.14, 16 bits).
3. **Truncation (REQ-05).** `t = p >>> 7` — drop the 7 LSBs with an arithmetic shift. This rounds toward minus infinity: `-1 x 1` (p = -1) gives `t = -1` (`0xff`), not 0. No round-to-nearest.
4. **Saturation (REQ-04).** If `t > 127`: `y = 127` (`0x7f`), `sat = 1`. If `t < -128`: `y = -128`, `sat = 1`. Otherwise `y = t`, `sat = 0`. Only `-1 x -1` reaches `t = 128`.
5. **Latency (REQ-02).** `y` and `sat` show the result one clock after the inputs were sampled.

## Corner cases (from the golden model)

| x | g | y | sat |
| --- | --- | --- | --- |
| `0x7f` (127/128) | `0x7f` | `0x7e` | 0 |
| `0x80` (-1) | `0x80` (-1) | `0x7f` | 1 |
| `0xff` (-1/128) | `0x01` (1/128) | `0xff` | 0 |
| `0x01` | `0x7f` | `0x00` | 0 |
