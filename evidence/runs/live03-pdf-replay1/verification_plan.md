# Verification plan · sync_fifo · live03-pdf-replay1

Every result below is **measured** (simulator output from stored files). No AI interpretation appears in this plan.

## Sources

| | |
| --- | --- |
| Run | `live03-pdf-replay1` · status `pass` · attempts 1 |
| Replay of | `live03-pdf` |
| Frozen suite | `4adc7da757edd72117db7a297aa7900d5744361903b2b9d1aea339da5dcc7db1` |
| Parameter sweep | `b73c1b823e400e72eaf76f91d72a90aa370f56711604f309f1037ed5710e16e2` |
| Requirements | `c7bdf104527e0183c374a59af5f7e70b7840f8b8f03f536ee39d569b3f8d22ec` |
| Mutant set | `3e17913c1b2117f60c4e2a69a6b28775d8ab5e2e4116b16c8fa46957baf68da1` |
| Final RTL | `466229822924bf013d4f9ca473df0c347c76a3d3e3cc825eb2e503d6678a863b` |
| Simulator | Icarus Verilog version 12.0 (stable) () |
| Parameters | WIDTH=8, DEPTH=16, AF_THRESH=14 |

## Gates at the final attempt

- **G1** static checks + `iverilog -g2001 -Wall`: ✓ Pass
- **G2** frozen suite: ✓ Pass 10/10
- **G3** parameter sweep (never shown to the model): ✓ Pass

## Requirements → tests → mutants → result

Requirements come from approved extraction `x-20261031-162122-f882` (approved by Claude (integration test, not a human review)). The *Maps to* link from each item to a REQ was proposed by the model (AI interpretation · not verified) and approved with the list; the test results are measured.

| Req | Requirement | Directed tests | Mutants targeting it | Attempt 1 | Final |
| --- | --- | --- | --- | --- | --- |
| EX-01 | All state changes occur on the rising edge of clk. | — | — | ○ No test | ○ No test |
| EX-02 | rst is a synchronous reset, active high. | — | — | ○ No test | ○ No test |
| EX-03 | dout is registered pop data, valid after the edge. | — | — | ○ No test | ○ No test |
| EX-04 → REQ-03 | full indicates occupancy is 16. | `test_full_flag`<br>`test_empty_flag` | M2 ✓ killed | ✓ Pass | ✓ Pass |
| EX-05 → REQ-03 | empty indicates occupancy is 0. | `test_full_flag`<br>`test_empty_flag` | M2 ✓ killed | ✓ Pass | ✓ Pass |
| EX-06 → REQ-08 | almost_full indicates occupancy at or above the almost-full level. | `test_almost_full` | M3 ✓ killed | ✓ Pass | ✓ Pass |
| EX-07 | overflow indicates push refused, high for one clock. | — | — | ○ No test | ○ No test |
| EX-08 | underflow indicates pop refused, high for one clock. | — | — | ○ No test | ○ No test |
| EX-09 → REQ-09 | count indicates words currently held. | `test_full_flag` | — | ✓ Pass | ✓ Pass |
| EX-10 → REQ-01 | At a rising edge with rst = 1, storage is emptied. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| EX-11 → REQ-01 | At a rising edge with rst = 1, count becomes 0. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| EX-12 → REQ-01 | At a rising edge with rst = 1, empty becomes 1. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| EX-13 → REQ-01 | At a rising edge with rst = 1, dout becomes 00h. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| EX-14 → REQ-01 | At a rising edge with rst = 1, overflow becomes 0. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| EX-15 → REQ-01 | At a rising edge with rst = 1, underflow becomes 0. | `test_reset_state` | M6 ✓ killed | ✓ Pass | ✓ Pass |
| EX-16 | A push when not full stores din and increments count by 1. | — | — | ○ No test | ○ No test |
| EX-17 → REQ-04 | A push while full with no pop is dropped and overflow pulses for one clock. | `test_overflow` | — | ✓ Pass | ✓ Pass |
| EX-18 | A pop when not empty makes the oldest word appear on dout and decrements count by 1. | — | — | ○ No test | ○ No test |
| EX-19 → REQ-05 | A pop while empty is ignored and dout keeps its old value. | `test_underflow` | M5 ✓ killed | ✓ Pass | ✓ Pass |
| EX-20 → REQ-05 | A pop while empty causes underflow to pulse for one clock. | `test_underflow` | M5 ✓ killed | ✓ Pass | ✓ Pass |
| EX-21 → REQ-06 | Push plus pop while full outputs the oldest word and stores the new word with count staying at 16. | `test_full_simultaneous_rw` | M1 ✓ killed | ✓ Pass | ✓ Pass |
| EX-22 | Push plus pop while full causes no overflow. | — | — | ○ No test | ○ No test |
| EX-23 → REQ-07 | Push plus pop while empty stores the word and the pop is ignored. | `test_empty_simultaneous_rw` | M7 ✓ killed | ✓ Pass | ✓ Pass |
| EX-24 → REQ-07 | Push plus pop while empty causes underflow to pulse. | `test_empty_simultaneous_rw` | M7 ✓ killed | ✓ Pass | ✓ Pass |
| EX-25 → REQ-06 | When holding 16 words with push and pop both high, each edge returns the oldest word on dout and stores din with count staying 16 and full staying 1. | `test_full_simultaneous_rw` | M1 ✓ killed | ✓ Pass | ✓ Pass |
| EX-26 | When push and pop are both high while full, overflow stays 0 because a pop frees the slot in the same cycle. | — | — | ○ No test | ○ No test |
| EX-27 | Pop only causes count to fall to 15 and full to drop. | — | — | ○ No test | ○ No test |
| EX-28 → REQ-02 | Words leave in the order they were pushed, including when the internal address wraps from entry 15 back to entry 0. | `test_wraparound_order` | M4 ✓ killed | ✓ Pass | ✓ Pass |
| EX-29 → REQ-08 | almost_full is high whenever count is 14 or more. | `test_almost_full` | M3 ✓ killed | ✓ Pass | ✓ Pass |

○ 10 item(s) have no test in the frozen suite: EX-01, EX-02, EX-03, EX-07, EX-08, EX-16, EX-18, EX-22, EX-26, EX-27.

Results are per test: a test shared by two requirements marks both rows.

`test_random_regression` runs 3000 random cycles against the golden model and covers EX-04, EX-05, EX-06, EX-09, EX-10, EX-11, EX-12, EX-13, EX-14, EX-15, EX-17, EX-19, EX-20, EX-21, EX-23, EX-24, EX-25, EX-28, EX-29. It is reported once here rather than in every row.

- Attempt 1: ✓ Pass
- Final: ✓ Pass

## Mutation check (qualifies the suite, measured against the reference RTL)

8/8 hand-written mutants killed.

Weak-test check: with `test_full_simultaneous_rw`, `test_random_regression` left out, 6/8 killed (survivors: M1, M8); restored suite 8/8.

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
| 1 | model | pass | 10/10 |
