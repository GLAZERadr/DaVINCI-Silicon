# Verification Plan format for DaVINCI (spec for task P1)

Researched 1 Nov 2026 from public industry sources (listed at the end). Goal: the exported plan should look like what a verification lead already expects, not a format we invented. Implemented by `verify/plan.py` (1 Nov).

## What the industry standard looks like

A verification plan (Vplan) maps every spec feature to test scenarios, coverage goals and sign-off criteria. It is written from the spec before RTL coding and updated as the design evolves (ChipVerify).

- Typical sections (ChipVerify): design overview and scope (including what is not verified), features to verify ("treat every 'shall' statement as a verification requirement"), methodology, test plan (test name, features targeted, directed/random, pass criteria, priority), coverage plan (code coverage + functional coverage), sign-off criteria, resources and schedule.
- Open-source reference format (OpenTitan testplan, Hjson): a list of testpoints, each with `name`, `milestone` (V1/V2/V3), `desc` (goal, stimulus, check) and `tests` (the runnable tests that cover it), plus a list of `covergroups` (`name`, `desc`). The tool maps regression results back onto testpoints to produce the results table.
- Sign-off is staged (OpenTitan DV checklist). V2 requires 90% nightly regression pass rate, 90% code coverage, 100% functional coverpoints and 75% crosses. V3 requires a 100% pass rate with 1 week soak, and 100% code and functional coverage.

## DaVINCI plan structure (what `verify/plan.py` generates)

Keep the industry shape, scaled to one block, and add the two things DaVINCI uniquely provides: mutation evidence and AI provenance.

1. **Header**: block name and parameters · spec file + hash · suite hash (`suite_sha256`) · simulator + version · date · run ID.
2. **Scope**: in scope, functional behaviour of `sync_fifo` per `spec/fifo_spec.md`. Out of scope (stated explicitly): timing/synthesis/power, CDC, formal proof, gate-level simulation.
3. **Methodology** (fixed text): cycle-accurate Python reference model compared on every clock (scoreboard) · directed tests per requirement · constrained-random regression (seed recorded) · mutation analysis to measure test strength · tests frozen before RTL generation; AI may only modify RTL.
4. **Testpoints table** (the core, one row per requirement; OpenTitan field names where they exist):

   | Field | Source |
   | --- | --- |
   | id (REQ-xx) | `spec/requirements.json` |
   | name (lower_snake_case feature) | derived from requirement |
   | milestone (V1/V2) | V1 = reset/basic flags, V2 = corner cases (full+rw, wrap, overflow/underflow) |
   | desc (goal · stimulus · check) | requirement text + test docstring |
   | tests | requirement → tests mapping |
   | result | latest `verdict.json`: pass / fail / unverified (no test) |
   | mutants | mutants targeting this REQ and killed/survived, from `mutation.json` |
   | scenario_hits | from `coverage.json` if P3 is done, else "not measured" |

5. **Coverage summary**: functional (scenario) coverage, hit / total scenarios, any at 0 hits (P3) · mutation score, killed / injected, survivors with their REQ · code coverage: "not measured" (Icarus has no built-in code coverage), said honestly rather than omitted.
6. **Sign-off status** (DaVINCI-scaled, modelled on OpenTitan V2), each line met / not met from real data only:
   - Every requirement has at least one test (no "unverified")
   - Full regression passes (all tests, recorded seed)
   - Mutation score 100% (no survivors)
   - All defined scenarios hit at least once (if P3 done)
   - Test suite unchanged since approval (suite hash matches)
7. **AI provenance** (DaVINCI-specific): model + provider · number of generation/repair attempts · each attempt's measured result · AI diagnoses labelled "AI interpretation · not verified" · cost.

## Output formats

- `verification_plan.md` (human-readable, all sections).
- `verification_plan.csv` (testpoints table only, opens in a spreadsheet).
- `testplan.hjson` in OpenTitan-like shape (testpoints: name, milestone, desc, tests; scenario counters as covergroups).
- `verification_plan.json` (everything, for the board).

## Rules

- Every number comes from files on disk. Missing data is shown as "not measured", never guessed.
- Do not claim code coverage, formal proof or timing results we do not have.

## Sources

- ChipVerify, Verification plan: https://www.chipverify.com/verification/verification-plan
- ChipVerify, Verification in the chip design flow: https://chipverify.com/verification/verification-in-chip-design-flow
- OpenTitan Testplanner tool (testplan Hjson format): https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/33d1b0fc873e90f0e4b66e527e072f0b09978a86/util/dvsim/doc/testplanner.md
- OpenTitan sign-off checklist (V1/V2/V3 DV criteria): https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/42765f88a7ba6ae6b7578906e098c40baed26ea8/doc/project/checklist.md
- Verification Academy, UART example test plan (purpose of a test plan; table is members-only): https://verificationacademy.com/cookbook/coverage/uart-example-test-plan
