# Verification plan · sync_fifo · live02-m1

Every result below is **measured** (simulator output from stored files). No AI interpretation appears in this plan.

## Sources

| | |
| --- | --- |
| Run | `live02-m1` · status `pass` · attempts 2 |
| Seeded bug | M1 (attempt 1 is the seeded RTL, not model output) |
| Frozen suite | `7d3b6b582d0aefaefee0c8a8fb24a0e7c107a77e5c2a2a8a987774626c1638a4` |
| Parameter sweep | — |
| Requirements | `7ba5f39c3e28a36b9c9248e13a07dbe5944ce2e5da36589997e7d471140850da` |
| Mutant set | `3e17913c1b2117f60c4e2a69a6b28775d8ab5e2e4116b16c8fa46957baf68da1` |
| Final RTL | `2f6f0748f1a46929bb1e74c05794950958fd3bcbd034277bc1c5873c3333f464` |
| Simulator | Icarus Verilog version 13.0 (stable) (v13_0) |
| Parameters | WIDTH=8, DEPTH=16, AF_THRESH=14 |

> ○ The requirements file differs from the one this run used.
> ○ The stored mutation check used a different frozen suite; mutant results are shown as unknown.
> ○ The stored weak-test check used a different frozen suite; it is left out.

## Gates at the final attempt

- **G1** static checks + `iverilog -g2001 -Wall`: ○ Not recorded
- **G2** frozen suite: ✓ Pass 10/10
- **G3** parameter sweep (never shown to the model): ○ Not recorded

## Requirements → tests → mutants → result

| Req | Requirement | Directed tests | Mutants targeting it | Attempt 1 | Final |
| --- | --- | --- | --- | --- | --- |
| REQ-01 | Synchronous reset empties the FIFO: count 0, empty 1, dout 0, overflow and underflow 0. | `test_reset_state` | M6 ○ Unknown | ✓ Pass | ✓ Pass |
| REQ-02 | Data is read out in the order it was written, including across pointer wraparound. | `test_wraparound_order` | M4 ○ Unknown | ✓ Pass | ✓ Pass |
| REQ-03 | full is 1 exactly when DEPTH entries are stored; empty is 1 exactly when none are. | `test_full_flag`<br>`test_empty_flag` | M2 ○ Unknown | ✓ Pass | ✓ Pass |
| REQ-04 | A write when full with no read is ignored and pulses overflow for one cycle. | `test_overflow` | — | ✓ Pass | ✓ Pass |
| REQ-05 | A read when empty is ignored, pulses underflow for one cycle, and dout holds its value. | `test_underflow` | M5 ○ Unknown | ✓ Pass | ✓ Pass |
| REQ-06 | Read and write in the same cycle when full: the oldest word is read, the new word is stored, count stays DEPTH. | `test_full_simultaneous_rw` | M1 ○ Unknown | ✕ Fail (`test_full_simultaneous_rw`) | ✓ Pass |
| REQ-07 | Read and write in the same cycle when empty: the word is stored, the read is ignored, underflow pulses. | `test_empty_simultaneous_rw` | M7 ○ Unknown | ✓ Pass | ✓ Pass |
| REQ-08 | almost_full is 1 exactly when count >= AF_THRESH. | `test_almost_full` | M3 ○ Unknown | ✓ Pass | ✓ Pass |
| REQ-09 | count equals the number of stored entries after every cycle. | `test_full_flag` | — | ✓ Pass | ✓ Pass |
| REQ-10 | A write when full together with a read in the same cycle is accepted: overflow stays 0. | `test_full_simultaneous_rw` | M8 ○ Unknown | ✕ Fail (`test_full_simultaneous_rw`) | ✓ Pass |

Results are per test: a test shared by two requirements marks both rows.

`test_random_regression` runs 3000 random cycles against the golden model and covers REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08, REQ-09, REQ-10. It is reported once here rather than in every row.

- Attempt 1: ✕ Fail (`test_random_regression`)
- Final: ✓ Pass

## Mutation check (qualifies the suite, measured against the reference RTL)

○ No mutation check for this suite hash.

## Scenario coverage (final RTL)

○ Not counted for this RTL (`make coverage RUN=<id>`, or `make coverage-ref`).

## Plan gaps (measured against the reference RTL)

○ No coverage-gap check for this suite hash (`make gaps`).

## Every attempt

| # | Source | Status | Frozen suite |
| --- | --- | --- | --- |
| 1 | seeded | fail | 8/10 |
| 2 | model | pass | 10/10 |
