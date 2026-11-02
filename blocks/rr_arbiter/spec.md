# rr_arbiter — specification

A 4-requester round-robin arbiter with a registered one-hot grant. This is the
spec the model receives; the frozen suite in `blocks/rr_arbiter/tests/` and its
golden model are the executable form of the same rules. Requirements
REQ-01..06 are listed in `blocks/rr_arbiter/requirements.json`.

## Interface

```verilog
module rr_arbiter (
    input  wire       clk,
    input  wire       rst,     // synchronous, active high
    input  wire [3:0] req,     // req[i] = requester i wants the resource
    output reg  [3:0] grant    // one-hot (or zero), registered
);
```

Port names, widths and directions are fixed. No parameters.

## Behaviour

Everything changes on the rising edge of `clk`; `req` is sampled at that edge.
The arbiter keeps a 2-bit priority pointer `ptr` (internal; its name is free).

1. **Reset (REQ-01).** If `rst` is 1: `grant = 0`, `ptr = 0`.
2. **Pick (REQ-05).** Look at requesters in the order `ptr, ptr+1, ptr+2, ptr+3` (mod 4); the first one with `req[i] = 1` wins.
3. **Grant (REQ-02, REQ-03).** If there is a winner `i`: `grant = 1 << i` and `ptr = (i + 1) mod 4`. Exactly one bit is set.
4. **No request (REQ-04).** If `req = 0`: `grant = 0` and `ptr` keeps its value. A bit of `grant` is never 1 unless the same bit of `req` was 1 at that edge.
5. **Fairness (REQ-06).** Follows from 2–3: a requester that holds `req[i]` high waits for at most the three others, so it is granted within 4 cycles.

## Example

| edge | req | grant after the edge | ptr after |
| --- | --- | --- | --- |
| reset | — | `0000` | 0 |
| 1 | `1111` | `0001` | 1 |
| 2 | `1111` | `0010` | 2 |
| 3 | `1001` | `1000` | 0 |
| 4 | `0000` | `0000` | 0 |
| 5 | `1001` | `0001` | 1 |
