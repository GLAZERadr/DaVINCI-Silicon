# Verification plan · sync_fifo · live03-pdf

Every result below is **measured** from stored simulator output, except the golden model's expected values (the reference) and the diagnoses in §7, which are labelled *AI interpretation · not verified*. Anything not measured says so.

Format: Vplan sections (ChipVerify) · OpenTitan testpoint fields · OpenTitan-style staged sign-off.

## 1. Header

| | |
| --- | --- |
| Block | `sync_fifo` · WIDTH=8, DEPTH=16, AF_THRESH=14 |
| Spec | `runs/_extract/x-20261031-162122-f882/interface_spec.md` · sha256 `13f46daa8c388fb4bc71732ce3224d9b157ab92fb0a81be7872965d529bf3956` |
| Frozen suite | `7d3b6b582d0aefaefee0c8a8fb24a0e7c107a77e5c2a2a8a987774626c1638a4` |
| Simulator | Icarus Verilog version 12.0 (stable) () |
| Date | 2026-10-31 |
| Run | `live03-pdf` · status `pass` · attempts 1 |
| Parameter sweep | — |
| Requirements | `c7bdf104527e0183c374a59af5f7e70b7840f8b8f03f536ee39d569b3f8d22ec` |
| Mutant set | `3e17913c1b2117f60c4e2a69a6b28775d8ab5e2e4116b16c8fa46957baf68da1` |
| Final RTL | `466229822924bf013d4f9ca473df0c347c76a3d3e3cc825eb2e503d6678a863b` |

> ○ The stored mutation check used a different frozen suite; mutant results are shown as unknown.

## 2. Scope

- **In scope:** functional behaviour of sync_fifo per runs/_extract/x-20261031-162122-f882/interface_spec.md.
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

Requirements come from approved extraction `x-20261031-162122-f882` (approved by Claude (integration test, not a human review)). The link from each item to a REQ (`EX-nn → REQ-nn`) was proposed by the model (AI interpretation · not verified) and approved with the list; test results are measured.

| ID | Name | MS | Goal · stimulus · check | Tests | Result | Mutants | Scenario hits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EX-01 | `all_state_changes_occur_on` | — | **Goal:** All state changes occur on the rising edge of clk.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-02 | `rst_is_a_synchronous_reset` | — | **Goal:** rst is a synchronous reset, active high.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-03 | `dout_is_registered_pop_data` | — | **Goal:** dout is registered pop data, valid after the edge.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-04 → REQ-03 | `full_empty_flags__ex04` | V1 | **Goal:** full indicates occupancy is 16.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored; test_empty_flag: empty asserts exactly when the last entry is read<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_empty_flag`<br>`test_random_regression` | ✓ Pass | M2 ○ Unknown | not measured |
| EX-05 → REQ-03 | `full_empty_flags__ex05` | V1 | **Goal:** empty indicates occupancy is 0.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored; test_empty_flag: empty asserts exactly when the last entry is read<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_empty_flag`<br>`test_random_regression` | ✓ Pass | M2 ○ Unknown | not measured |
| EX-06 → REQ-08 | `almost_full_threshold__ex06` | V1 | **Goal:** almost_full indicates occupancy at or above the almost-full level.<br>**Stimulus:** test_almost_full: almost_full is high exactly when count >= AF_THRESH<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_almost_full`<br>`test_random_regression` | ✓ Pass | M3 ○ Unknown | not measured |
| EX-07 | `overflow_indicates_push_refused_high` | — | **Goal:** overflow indicates push refused, high for one clock.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-08 | `underflow_indicates_pop_refused_high` | — | **Goal:** underflow indicates pop refused, high for one clock.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-09 → REQ-09 | `count_tracks_occupancy__ex09` | V1 | **Goal:** count indicates words currently held.<br>**Stimulus:** test_full_flag: full asserts exactly when DEPTH entries are stored<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_flag`<br>`test_random_regression` | ✓ Pass | — | not measured |
| EX-10 → REQ-01 | `reset_state__ex10` | V1 | **Goal:** At a rising edge with rst = 1, storage is emptied.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| EX-11 → REQ-01 | `reset_state__ex11` | V1 | **Goal:** At a rising edge with rst = 1, count becomes 0.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| EX-12 → REQ-01 | `reset_state__ex12` | V1 | **Goal:** At a rising edge with rst = 1, empty becomes 1.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| EX-13 → REQ-01 | `reset_state__ex13` | V1 | **Goal:** At a rising edge with rst = 1, dout becomes 00h.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| EX-14 → REQ-01 | `reset_state__ex14` | V1 | **Goal:** At a rising edge with rst = 1, overflow becomes 0.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| EX-15 → REQ-01 | `reset_state__ex15` | V1 | **Goal:** At a rising edge with rst = 1, underflow becomes 0.<br>**Stimulus:** test_reset_state: after reset the FIFO is empty, count 0, dout 0, no flags<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_reset_state`<br>`test_random_regression` | ✓ Pass | M6 ○ Unknown | not measured |
| EX-16 | `a_push_when_not_full` | — | **Goal:** A push when not full stores din and increments count by 1.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-17 → REQ-04 | `overflow_write_when_full__ex17` | V2 | **Goal:** A push while full with no pop is dropped and overflow pulses for one clock.<br>**Stimulus:** test_overflow: a write when full (no read) is ignored and flags overflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_overflow`<br>`test_random_regression` | ✓ Pass | — | not measured |
| EX-18 | `a_pop_when_not_empty` | — | **Goal:** A pop when not empty makes the oldest word appear on dout and decrements count by 1.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-19 → REQ-05 | `underflow_read_when_empty__ex19` | V2 | **Goal:** A pop while empty is ignored and dout keeps its old value.<br>**Stimulus:** test_underflow: a read when empty is ignored, flags underflow, dout holds<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_underflow`<br>`test_random_regression` | ✓ Pass | M5 ○ Unknown | not measured |
| EX-20 → REQ-05 | `underflow_read_when_empty__ex20` | V2 | **Goal:** A pop while empty causes underflow to pulse for one clock.<br>**Stimulus:** test_underflow: a read when empty is ignored, flags underflow, dout holds<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_underflow`<br>`test_random_regression` | ✓ Pass | M5 ○ Unknown | not measured |
| EX-21 → REQ-06 | `read_write_when_full__ex21` | V2 | **Goal:** Push plus pop while full outputs the oldest word and stores the new word with count staying at 16.<br>**Stimulus:** test_full_simultaneous_rw: read + write when full reads the oldest, stores the new word<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_simultaneous_rw`<br>`test_random_regression` | ✓ Pass | M1 ○ Unknown | not measured |
| EX-22 | `push_plus_pop_while_full` | — | **Goal:** Push plus pop while full causes no overflow.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-23 → REQ-07 | `read_write_when_empty__ex23` | V2 | **Goal:** Push plus pop while empty stores the word and the pop is ignored.<br>**Stimulus:** test_empty_simultaneous_rw: read + write when empty stores the word and flags underflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_empty_simultaneous_rw`<br>`test_random_regression` | ✓ Pass | M7 ○ Unknown | not measured |
| EX-24 → REQ-07 | `read_write_when_empty__ex24` | V2 | **Goal:** Push plus pop while empty causes underflow to pulse.<br>**Stimulus:** test_empty_simultaneous_rw: read + write when empty stores the word and flags underflow<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_empty_simultaneous_rw`<br>`test_random_regression` | ✓ Pass | M7 ○ Unknown | not measured |
| EX-25 → REQ-06 | `read_write_when_full__ex25` | V2 | **Goal:** When holding 16 words with push and pop both high, each edge returns the oldest word on dout and stores din with count staying 16 and full staying 1.<br>**Stimulus:** test_full_simultaneous_rw: read + write when full reads the oldest, stores the new word<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_full_simultaneous_rw`<br>`test_random_regression` | ✓ Pass | M1 ○ Unknown | not measured |
| EX-26 | `when_push_and_pop_are` | — | **Goal:** When push and pop are both high while full, overflow stays 0 because a pop frees the slot in the same cycle.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-27 | `pop_only_causes_count_to` | — | **Goal:** Pop only causes count to fall to 15 and full to drop.<br>**Stimulus:** no test<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | — | unverified | — | not measured |
| EX-28 → REQ-02 | `fifo_order_wraparound__ex28` | V2 | **Goal:** Words leave in the order they were pushed, including when the internal address wraps from entry 15 back to entry 0.<br>**Stimulus:** test_wraparound_order: data leaves in write order across pointer wraparound<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_wraparound_order`<br>`test_random_regression` | ✓ Pass | M4 ○ Unknown | not measured |
| EX-29 → REQ-08 | `almost_full_threshold__ex29` | V1 | **Goal:** almost_full is high whenever count is 14 or more.<br>**Stimulus:** test_almost_full: almost_full is high exactly when count >= AF_THRESH<br>**Check:** every output compared with the cycle-accurate golden model on every clock (scoreboard) | `test_almost_full`<br>`test_random_regression` | ✓ Pass | M3 ○ Unknown | not measured |

`test_random_regression` (3000 random cycles, seed 20261105) covers EX-04, EX-05, EX-06, EX-09, EX-10, EX-11, EX-12, EX-13, EX-14, EX-15, EX-17, EX-19, EX-20, EX-21, EX-23, EX-24, EX-25, EX-28, EX-29; a test shared by several requirements marks each of them. Attempt 1: ✓ Pass · final: ✓ Pass.

## 5. Coverage summary

- **Functional (scenario) coverage:** not measured
- **Mutation score:** not measured
- **Code coverage:** not measured (Icarus Verilog has no built-in code coverage).

## 6. Sign-off status

DaVINCI-scaled, modelled on OpenTitan's V2 checklist. Each line is met / not met from stored data, or not measured.

| Criterion | Status | Evidence |
| --- | --- | --- |
| Every requirement has at least one test (no "unverified") | ✕ not met | 19/29 testpoints have tests |
| Full regression passes (all tests, recorded seed) | ✓ met | 10/10 tests at the final attempt, random seed 20261105 |
| Mutation score 100% (no survivors) | ○ not measured | no mutation check for this suite hash |
| All defined scenarios hit at least once | ○ not measured | scenario counts not taken for this RTL |
| Test suite unchanged since approval (suite hash matches) | ✕ not met | run used 7d3b6b582d0a…, current pin 4adc7da757ed… (suite changed after this run) |

Run gates at the final attempt: **G1** static checks + `iverilog -g2001 -Wall` ○ Not recorded · **G2** frozen suite ✓ Pass 10/10 · **G3** parameter sweep (never shown to the model) ○ Not recorded.

## 7. AI provenance

Model(s): muse-spark-1.3 · providers: generate `meta`, repair `meta` · total cost $0.0509 · 2,646 in / 11,195 out tokens (measured, from the ledger).

| # | Source | Model | Status | Frozen suite | Tokens in/out | Cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | model | muse-spark-1.3 | pass | 10/10 | 2,646/11,195 | $0.0509 |
