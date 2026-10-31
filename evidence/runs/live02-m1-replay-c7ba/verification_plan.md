# Verification plan · sync_fifo · live02-m1-replay-c7ba

Every result below is **measured** (simulator output from stored files). No AI interpretation appears in this plan.

## Sources

| | |
| --- | --- |
| Run | `live02-m1-replay-c7ba` · status `pass` · attempts 2 |
| Seeded bug | M1 (attempt 1 is the seeded RTL, not model output) |
| Replay of | `live02-m1` |
| Frozen suite | `4adc7da757edd72117db7a297aa7900d5744361903b2b9d1aea339da5dcc7db1` |
| Parameter sweep | `b73c1b823e400e72eaf76f91d72a90aa370f56711604f309f1037ed5710e16e2` |
| Requirements | `7ba5f39c3e28a36b9c9248e13a07dbe5944ce2e5da36589997e7d471140850da` |
| Mutant set | `3e17913c1b2117f60c4e2a69a6b28775d8ab5e2e4116b16c8fa46957baf68da1` |
| Final RTL | `2f6f0748f1a46929bb1e74c05794950958fd3bcbd034277bc1c5873c3333f464` |
| Simulator | Icarus Verilog version 12.0 (stable) () |
| Parameters | WIDTH=8, DEPTH=16, AF_THRESH=14 |

## Gates at the final attempt

- **G1** static checks + `iverilog -g2001 -Wall`: ✓ Pass
- **G2** frozen suite: ✓ Pass 10/10
- **G3** parameter sweep (never shown to the model): ✓ Pass

## Requirements → tests → mutants → result

| Req | Requirement | Directed tests | Mutants targeting it | Attempt 1 | Final |
| --- | --- | --- | --- | --- | --- |
| REQ-01 | Synchronous reset empties the FIFO: count 0, empty 1, dout 0, overflow and underflow 0. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| REQ-02 | Data is read out in the order it was written, including across pointer wraparound. | `test_wraparound_order` | M4 ✓ killed | ✓ Pass | ✓ Pass |
| REQ-03 | full is 1 exactly when DEPTH entries are stored; empty is 1 exactly when none are. | `test_full_flag`<br>`test_empty_flag` | M2 ✓ killed | ✓ Pass | ✓ Pass |
| REQ-04 | A write when full with no read is ignored and pulses overflow for one cycle. | `test_overflow` | — | ✓ Pass | ✓ Pass |
| REQ-05 | A read when empty is ignored, pulses underflow for one cycle, and dout holds its value. | `test_underflow` | M5 ✓ killed | ✓ Pass | ✓ Pass |
| REQ-06 | Read and write in the same cycle when full: the oldest word is read, the new word is stored, count stays DEPTH. | `test_full_simultaneous_rw` | M1 ✓ killed | ✕ Fail (`test_full_simultaneous_rw`) | ✓ Pass |
| REQ-07 | Read and write in the same cycle when empty: the word is stored, the read is ignored, underflow pulses. | `test_empty_simultaneous_rw` | M7 ✓ killed | ✓ Pass | ✓ Pass |
| REQ-08 | almost_full is 1 exactly when count >= AF_THRESH. | `test_almost_full` | M3 ✓ killed | ✓ Pass | ✓ Pass |
| REQ-09 | count equals the number of stored entries after every cycle. | `test_full_flag` | — | ✓ Pass | ✓ Pass |
| REQ-10 | A write when full together with a read in the same cycle is accepted: overflow stays 0. | `test_full_simultaneous_rw` | M8 ✓ killed | ✕ Fail (`test_full_simultaneous_rw`) | ✓ Pass |

Results are per test: a test shared by two requirements marks both rows.

`test_random_regression` runs 3000 random cycles against the golden model and covers REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08, REQ-09, REQ-10. It is reported once here rather than in every row.

- Attempt 1: ✕ Fail (`test_random_regression`)
- Final: ✓ Pass

## Mutation check (qualifies the suite, measured against the reference RTL)

8/8 hand-written mutants killed.

Weak-test check: with `test_full_simultaneous_rw`, `test_random_regression` left out, 6/8 killed (survivors: M1, M8); restored suite 8/8.

## Scenario coverage (final RTL)

How often the frozen suite drove the final RTL into each situation, counted at every rising clock edge over 3253 cycles from a waveform of the same tests (`verify/coverage.py`, flags as the design reported them).

| Scenario | Count |
| --- | --- |
| rst high at the edge | 29 |
| full high | 67 |
| empty high | 320 |
| almost_full high | 213 |
| write, no read, while full (overflow case) | 22 |
| read while empty (underflow case) | 141 |
| read and write together while full | 10 |
| read and write together while empty | 48 |
| overflow output high | 22 |
| underflow output high | 141 |
| accepted writes since reset reach a multiple of DEPTH=16 | 96 |

Never reached: none.

## Plan gaps (measured against the reference RTL)

- Mutants caught by only one directed test: M1, M8
- Mutants caught only by the random regression: none
- Requirements no mutant targets (nothing shows their tests would catch a bug): REQ-04, REQ-09
- Re-simulated with tests left out: 19 suites; prediction from the full run's killers matched every one.

| Mutant | Targets | Directed tests that kill it | Killed by its own requirement's tests |
| --- | --- | --- | --- |
| M1 | REQ-06 | `test_full_simultaneous_rw` ○ only one | `test_full_simultaneous_rw` |
| M2 | REQ-03 | `test_almost_full`, `test_full_flag`, `test_full_simultaneous_rw`, `test_overflow`, `test_wraparound_order` | `test_full_flag` |
| M3 | REQ-08 | `test_almost_full`, `test_full_flag`, `test_full_simultaneous_rw`, `test_overflow`, `test_wraparound_order` | `test_almost_full` |
| M4 | REQ-02 | `test_almost_full`, `test_full_simultaneous_rw`, `test_overflow`, `test_wraparound_order` | `test_wraparound_order` |
| M5 | REQ-05 | `test_empty_simultaneous_rw`, `test_underflow` | `test_underflow` |
| M6 | REQ-01 | `test_almost_full`, `test_empty_flag`, `test_empty_simultaneous_rw`, `test_full_flag`, `test_full_simultaneous_rw`, `test_overflow`, `test_reset_state`, `test_underflow`, `test_wraparound_order` | `test_reset_state` |
| M7 | REQ-07 | `test_empty_simultaneous_rw`, `test_underflow` | `test_empty_simultaneous_rw` |
| M8 | REQ-10 | `test_full_simultaneous_rw` ○ only one | `test_full_simultaneous_rw` |

Suites that let a mutant survive:

| Left out | Killed | Survivors |
| --- | --- | --- |
| `test_full_simultaneous_rw`, `test_random_regression` | 6/8 | ✕ M1, M8 |

## Every attempt

| # | Source | Status | Frozen suite |
| --- | --- | --- | --- |
| 1 | seeded | fail | 8/10 |
| 2 | model | pass | 10/10 |
