# Verification plan · sync_fifo · live02-m1

Every result below is **measured** from stored simulator output, except the golden model's expected values (the reference) and the diagnoses in §7, which are labelled *AI interpretation · not verified*. Anything not measured says so.

Format: Vplan sections (ChipVerify) · OpenTitan testpoint fields · OpenTitan-style staged sign-off.

## 1. Header

| | |
| --- | --- |
| Block | `sync_fifo` · WIDTH=8, DEPTH=16, AF_THRESH=14 |
| Spec | `spec/fifo_spec.md` · sha256 `cc9459ba56ef28436ebf8b18b15e1f770a95cb7cb53bd462fdd18d4d1574d156` · ○ the current file differs from the spec this run recorded |
| Frozen suite | `7d3b6b582d0aefaefee0c8a8fb24a0e7c107a77e5c2a2a8a987774626c1638a4` |
| Simulator | Icarus Verilog version 13.0 (stable) (v13_0) |
| Date | 2026-10-31 |
| Run | `live02-m1` · status `pass` · attempts 2 |
| Seeded bug | M1 (attempt 1 is the seeded RTL, not model output) |
| Parameter sweep | — |
| Requirements | `7ba5f39c3e28a36b9c9248e13a07dbe5944ce2e5da36589997e7d471140850da` |
| Mutant set | `3e17913c1b2117f60c4e2a69a6b28775d8ab5e2e4116b16c8fa46957baf68da1` |
| Final RTL | `2f6f0748f1a46929bb1e74c05794950958fd3bcbd034277bc1c5873c3333f464` |

> ○ The requirements file differs from the one this run used.
> ○ The stored mutation check used a different frozen suite; mutant results are shown as unknown.

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
| REQ-01 | `reset_state` | V1 | **Goal:** Synchronous reset empties the FIFO: count 0, empty 1, dout 0, overflow and underflow 0.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| REQ-02 | `fifo_order_wraparound` | V2 | **Goal:** Data is read out in the order it was written, including across pointer wraparound.<br>**Stimulus:** test_wraparound_order: data leaves in write order across pointer wraparound<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_wraparound_order`<br>`test_random_regression` | ✓ Pass | M4 ○ Unknown | not measured |
| REQ-03 | `full_empty_flags` | V1 | **Goal:** full is 1 exactly when DEPTH entries are stored; empty is 1 exactly when none are.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored; test_empty_flag: empty asserts exactly when the last entry is read<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_empty_flag`<br>`test_random_regression` | ✓ Pass | M2 ○ Unknown | not measured |
| REQ-04 | `overflow_write_when_full` | V2 | **Goal:** A write when full with no read is ignored and pulses overflow for one cycle.<br>**Stimulus:** test_overflow: a write when full (no read) is ignored and flags overflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_overflow`<br>`test_random_regression` | ✓ Pass | — | not measured |
| REQ-05 | `underflow_read_when_empty` | V2 | **Goal:** A read when empty is ignored, pulses underflow for one cycle, and dout holds its value.<br>**Stimulus:** test_underflow: a read when empty is ignored, flags underflow, dout holds<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_underflow`<br>`test_random_regression` | ✓ Pass | M5 ○ Unknown | not measured |
| REQ-06 | `read_write_when_full` | V2 | **Goal:** Read and write in the same cycle when full: the oldest word is read, the new word is stored, count stays DEPTH.<br>**Stimulus:** test_full_simultaneous_rw: read + write when full reads the oldest, stores the new word<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_simultaneous_rw`<br>`test_random_regression` | ✓ Pass (attempt 1: ✕ Fail) | M1 ○ Unknown | not measured |
| REQ-07 | `read_write_when_empty` | V2 | **Goal:** Read and write in the same cycle when empty: the word is stored, the read is ignored, underflow pulses.<br>**Stimulus:** test_empty_simultaneous_rw: read + write when empty stores the word and flags underflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_empty_simultaneous_rw`<br>`test_random_regression` | ✓ Pass | M7 ○ Unknown | not measured |
| REQ-08 | `almost_full_threshold` | V1 | **Goal:** almost_full is 1 exactly when count >= AF_THRESH.<br>**Stimulus:** test_almost_full: almost_full is high exactly when count >= AF_THRESH<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_almost_full`<br>`test_random_regression` | ✓ Pass | M3 ○ Unknown | not measured |
| REQ-09 | `count_tracks_occupancy` | V1 | **Goal:** count equals the number of stored entries after every cycle.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_random_regression` | ✓ Pass | — | not measured |
| REQ-10 | `no_overflow_read_write_when_full` | V2 | **Goal:** A write when full together with a read in the same cycle is accepted: overflow stays 0.<br>**Stimulus:** test_full_simultaneous_rw: read + write when full reads the oldest, stores the new word<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_simultaneous_rw`<br>`test_random_regression` | ✓ Pass (attempt 1: ✕ Fail) | M8 ○ Unknown | not measured |

`test_random_regression` (3000 random cycles, seed 20261105) covers REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07, REQ-08, REQ-09, REQ-10; a test shared by several requirements marks each of them. Attempt 1: ✕ Fail (`test_random_regression`) · final: ✓ Pass.

## 5. Coverage summary

- **Functional (scenario) coverage:** not measured
- **Mutation score:** not measured
- **Code coverage:** not measured (Icarus Verilog has no built-in code coverage).

## 6. Sign-off status

DaVINCI-scaled, modelled on OpenTitan's V2 checklist. Each line is met / not met from stored data, or not measured.

| Criterion | Status | Evidence |
| --- | --- | --- |
| Every requirement has at least one test (no "unverified") | ✓ met | 10/10 testpoints have tests |
| Full regression passes (all tests, recorded seed) | ✓ met | 10/10 tests at the final attempt, random seed 20261105 |
| Mutation score 100% (no survivors) | ○ not measured | no mutation check for this suite hash |
| All defined scenarios hit at least once | ○ not measured | scenario counts not taken for this RTL |
| Test suite unchanged since approval (suite hash matches) | ✕ not met | run used 7d3b6b582d0a…, current pin 4adc7da757ed… (suite changed after this run) |

Run gates at the final attempt: **G1** static checks + `iverilog -g2001 -Wall` ○ Not recorded · **G2** frozen suite ✓ Pass 10/10 · **G3** parameter sweep (never shown to the model) ○ Not recorded.

## 7. AI provenance

Model(s): muse-spark-1.3 · providers: generate `meta`, repair `meta` · total cost $0.0079 · 2,131 in / 1,241 out tokens (measured, from the ledger).

| # | Source | Model | Status | Frozen suite | Tokens in/out | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | seeded | — | fail | 8/10 | — | — |
| 2 | model | muse-spark-1.3 | pass | 10/10 | 2,131/1,241 | $0.0079 |

Diagnoses (*AI interpretation · not verified*):

> **Attempt 2 · muse-spark-1.3:** `do_write` was `wr_en && !full`, so a simultaneous read+write when full dropped the write and decremented `count`; spec requires `do_write = wr_en && (!full || rd_en)` so both pointers advance and count stays at DEPTH.
