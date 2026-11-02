# Verification plan · sync_fifo · live02-m1-replay8

Every result below is **measured** from stored simulator output, except the golden model's expected values (the reference) and the diagnoses in §7, which are labelled *AI interpretation · not verified*. Anything not measured says so.

Format: Vplan sections (ChipVerify) · OpenTitan testpoint fields · OpenTitan-style staged sign-off.

## 1. Header

| | |
| --- | --- |
| Block | `sync_fifo` · WIDTH=8, DEPTH=16, AF_THRESH=14 |
| Spec | `spec/fifo_spec.md` · sha256 `6e04e4641dc412f506396b1271441ba94d847eac5ec86a121431dbc465444126` |
| Frozen suite | `4adc7da757edd72117db7a297aa7900d5744361903b2b9d1aea339da5dcc7db1` |
| Simulator | Icarus Verilog version 12.0 (stable) () |
| Date | 2026-11-02 |
| Run | `live02-m1-replay8` · status `pass` · attempts 2 |
| Seeded bug | M1 (attempt 1 is the seeded RTL, not model output) |
| Replay of | `live02-m1` |
| Parameter sweep | `b73c1b823e400e72eaf76f91d72a90aa370f56711604f309f1037ed5710e16e2` |
| Requirements | `7ba5f39c3e28a36b9c9248e13a07dbe5944ce2e5da36589997e7d471140850da` |
| Mutant set | `3e17913c1b2117f60c4e2a69a6b28775d8ab5e2e4116b16c8fa46957baf68da1` |
| Final RTL | `2f6f0748f1a46929bb1e74c05794950958fd3bcbd034277bc1c5873c3333f464` |

## 2. Scope

- **In scope:** functional behaviour of sync_fifo per spec/fifo_spec.md.
- **Out of scope:** timing, synthesis, area and power; clock-domain crossing (single clock by design); formal proof; gate-level simulation; code coverage (Icarus Verilog has no built-in code coverage).

## 3. Methodology

- cycle-accurate Python reference model compared on every clock (scoreboard)
- directed tests per requirement
- constrained-random regression, 3000 cycles, seed 20261105
- mutation analysis with hand-written mutants to measure test strength
- tests frozen and hash-pinned before RTL generation; the AI may only change RTL
- parameter sweep at other WIDTH/DEPTH/AF_THRESH sets, never shown to the model

## 4. Testpoints

Milestones: **V1** reset and basic flags · **V2** corner cases (full with read/write, wraparound, overflow/underflow). Result is the final attempt; a different attempt-1 result is noted.

| ID | Name | MS | Goal · stimulus · check | Tests | Result | Mutants | Scenario hits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-01 | `reset_state` | V1 | **Goal:** Synchronous reset empties the FIFO: count 0, empty 1, dout 0, overflow and underflow 0.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ✓ killed | reset 29 |
| REQ-02 | `fifo_order_wraparound` | V2 | **Goal:** Data is read out in the order it was written, including across pointer wraparound.<br>**Stimulus:** test_wraparound_order: data leaves in write order across pointer wraparound<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_wraparound_order`<br>`test_random_regression` | ✓ Pass | M4 ✓ killed | write_pointer_wrap 96 |
| REQ-03 | `full_empty_flags` | V1 | **Goal:** full is 1 exactly when DEPTH entries are stored; empty is 1 exactly when none are.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored; test_empty_flag: empty asserts exactly when the last entry is read<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_empty_flag`<br>`test_random_regression` | ✓ Pass | M2 ✓ killed | full 67, empty 320 |
| REQ-04 | `overflow_write_when_full` | V2 | **Goal:** A write when full with no read is ignored and pulses overflow for one cycle.<br>**Stimulus:** test_overflow: a write when full (no read) is ignored and flags overflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_overflow`<br>`test_random_regression` | ✓ Pass | — | write_when_full 22, overflow_pulse 22 |
| REQ-05 | `underflow_read_when_empty` | V2 | **Goal:** A read when empty is ignored, pulses underflow for one cycle, and dout holds its value.<br>**Stimulus:** test_underflow: a read when empty is ignored, flags underflow, dout holds<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_underflow`<br>`test_random_regression` | ✓ Pass | M5 ✓ killed | read_when_empty 141, underflow_pulse 141 |
| REQ-06 | `read_write_when_full` | V2 | **Goal:** Read and write in the same cycle when full: the oldest word is read, the new word is stored, count stays DEPTH.<br>**Stimulus:** test_full_simultaneous_rw: read + write when full reads the oldest, stores the new word<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_simultaneous_rw`<br>`test_random_regression` | ✓ Pass (attempt 1: ✕ Fail) | M1 ✓ killed | rw_when_full 10 |
| REQ-07 | `read_write_when_empty` | V2 | **Goal:** Read and write in the same cycle when empty: the word is stored, the read is ignored, underflow pulses.<br>**Stimulus:** test_empty_simultaneous_rw: read + write when empty stores the word and flags underflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_empty_simultaneous_rw`<br>`test_random_regression` | ✓ Pass | M7 ✓ killed | rw_when_empty 48 |
| REQ-08 | `almost_full_threshold` | V1 | **Goal:** almost_full is 1 exactly when count >= AF_THRESH.<br>**Stimulus:** test_almost_full: almost_full is high exactly when count >= AF_THRESH<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_almost_full`<br>`test_random_regression` | ✓ Pass | M3 ✓ killed | almost_full 213 |
| REQ-09 | `count_tracks_occupancy` | V1 | **Goal:** count equals the number of stored entries after every cycle.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_random_regression` | ✓ Pass | — | no scenario defined |
| REQ-10 | `no_overflow_read_write_when_full` | V2 | **Goal:** A write when full together with a read in the same cycle is accepted: overflow stays 0.<br>**Stimulus:** test_full_simultaneous_rw: read + write when full reads the oldest, stores the new word<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_simultaneous_rw`<br>`test_random_regression` | ✓ Pass (attempt 1: ✕ Fail) | M8 ✓ killed | rw_when_full 10 |

`test_random_regression` (3000 random cycles, seed 20261105) covers REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08, REQ-09, REQ-10; a test shared by several requirements marks each of them. Attempt 1: ✕ Fail (`test_random_regression`) · final: ✓ Pass.

## 5. Coverage summary

- **Functional (scenario) coverage:** 11/11 scenarios hit; at 0 hits: none
- **Mutation score:** 8/8 killed; survivors: none (hand-written mutants in the reference RTL; describes the suite, not this RTL)
- **Code coverage:** not measured (Icarus Verilog has no built-in code coverage).

### 5.1 Scenario counts (final RTL, 3253 cycles, `verify/coverage.py`)

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

### 5.2 Weak-test check

With `test_full_simultaneous_rw`, `test_random_regression` left out, 6/8 killed (survivors: M1, M8); restored suite 8/8.

### 5.3 Test-plan gaps (mutation analysis with tests left out)

- Mutants caught by only one directed test: M1, M8
- Mutants caught only by the random regression: none
- Requirements no mutant targets: REQ-04, REQ-09
- 19 suites re-simulated with tests left out; prediction from the full run's killers matched every one.
- Without `test_full_simultaneous_rw`, `test_random_regression`: 6/8 killed, ✕ M1, M8 survive

## 6. Sign-off status

DaVINCI-scaled, modelled on OpenTitan's V2 checklist. Each line is met / not met from stored data, or not measured.

| Criterion | Status | Evidence |
| --- | --- | --- |
| Every requirement has at least one test (no "unverified") | ✓ met | 10/10 testpoints have tests |
| Full regression passes (all tests, recorded seed) | ✓ met | 10/10 tests at the final attempt, random seed 20261105 |
| Mutation score 100% (no survivors) | ✓ met | 8/8 killed |
| All defined scenarios hit at least once | ✓ met | 11/11 scenarios hit |
| Test suite unchanged since approval (suite hash matches) | ✓ met | run suite equals the current pin |

Run gates at the final attempt: **G1** static checks + `iverilog -g2001 -Wall` ✓ Pass · **G2** frozen suite ✓ Pass 10/10 · **G3** parameter sweep (never shown to the model) ✓ Pass.

## 7. AI provenance

Model(s): replay:muse-spark-1.3 · providers: generate `replay`, repair `replay` · total cost $0.0000 · 0 in / 0 out tokens (measured, from the ledger).

| # | Source | Model | Status | Frozen suite | Tokens in/out | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seeded | — | fail | 8/10 | — | — |
| 2 | model | replay:muse-spark-1.3 | pass | 10/10 | 0/0 | $0.0000 |

Diagnoses (*AI interpretation · not verified*):

> **Attempt 2 · replay:muse-spark-1.3:** `do_write` was `wr_en && !full`, so a simultaneous read+write when full dropped the write and decremented `count`; spec requires `do_write = wr_en && (!full || rd_en)` so both pointers advance and count stays at DEPTH.
