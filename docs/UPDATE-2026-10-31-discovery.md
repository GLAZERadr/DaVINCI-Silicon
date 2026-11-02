# Update 31 Oct 2026: engineer discovery → verification plan + evidence

Overrides older priorities in the engineering handover where they conflict. Applies to work on Mon 2 – Tue 3 Nov, before UI polish and before feature freeze (3 Nov 23:59 WIB).

## 1. What we heard

Two practising hardware engineers answered two questions: what is hardest in RTL work, and where do learners struggle. They are anonymised here. No names or quotes go in the README, UI or video without Adrian's confirmation.

| | Engineer A (industry design background) | Engineer B (FPGA prototyping, audio DSP on Kria KV260) |
| --- | --- | --- |
| Writing RTL | Easy: a translation of a design already broken down. AI can do it given the design. | Hard |
| Design breakdown (spec → microarchitecture) | The hardest part | — |
| Testbench | Not hard on its own; in a company, coverage and a **verification plan** are required, and that is "as complicated as the design itself" | Hard |
| Debugging | Hard everywhere | — |
| Timing closure | — | Hard (timing slack) |
| Learners | Treat hardware like software, copy and paste without knowing what they build | — |

Two people is a lead, not a finding. Nothing here becomes a number or a claim.

## 2. What changes

**Headline:** from "AI writes RTL" to **"a verification plan with evidence: every requirement traced to frozen tests, proven by mutation, with every AI attempt measured"**. RTL generation stays, but as the thing being checked, not the selling point.

What already supports it: the frozen suite and golden model, requirement → test traceability (`spec/requirements.json`), 8/8 mutants killed, the weak-test demo, G1–G3 gates, and the measured-vs-AI split on the Evidence Board.

What we will state as limitations, not build:
- **Design breakdown** is done by a person: the requirements and `spec/interface.json` are human-written and human-approved.
- **Timing / synthesis**: there is no synthesis or timing analysis. Scope stays at one block and one simulator.

## 3. New tasks

All four must leave `tests/`, `verify/suite.sha256` and `verify/sweep.sha256` unchanged. They cost $0 in model calls (they read stored runs and simulator output).

### P1 – Verification Plan export
A generated plan document per run, and one for the reference RTL.
- Source data only: `spec/requirements.json`, `verify/mutants.json`, the mutation result, the weak-demo result, and the run's `verdict.json`.
- Per requirement: text, directed tests, the random regression, mutants that target it and whether each was killed, P3 scenario counts, and the result at attempt 1 and at the final attempt.
- Header: suite hash, sweep hash, simulator version, run id, date. Every value labelled measured.
- Output: `verification_plan.md` and `verification_plan.json` next to `run.json`, a `make plan` target, included in the evidence bundle, and a download link on the Evidence Board.
- Done when: the export is reproducible byte-for-byte from the stored run, and a hand check on `live02-m1` matches the board.

- **Format update (1 Nov):** the plan now follows `docs/verification-plan-format.md` (Vplan sections, OpenTitan testpoints, staged sign-off, AI provenance) and is also written as `verification_plan.csv` and `testplan.hjson`.

### P2 – Coverage-gap mode
Show where the plan is weak instead of only where the RTL fails.
- For each requirement: which mutants only one test kills (a single point of failure), and which requirements have no directed test of their own (covered only by the random regression).
- Generalise the weak-test demo: drop each directed test in turn, re-run the mutation check, and report which mutants survive. 10 suite runs × 8 mutants, run in the sandbox, results stored in `runs/coverage_gap/`.
- Output: a "Plan gaps" section in P1 and on the board, labelled measured.
- Done when: dropping `test_full_simultaneous_rw` reproduces the known result (M1 and M8 survive), and the full-suite row shows 8/8.
- **Result (31 Oct, `make gaps`, 37 s, local):** full suite 8/8. Leaving out any single test: no survivors (the random regression catches every mutant). Leaving out `test_full_simultaneous_rw` together with the random regression: M1 and M8 survive (6/8), the same as the weak-test demo; every other directed test is backed up. M1 and M8 have only one directed killer. REQ-04 and REQ-09 have no mutant, so nothing shows their tests would catch a bug. All 19 re-simulated suites matched the prediction from the full run's killers. The original criterion was imprecise: dropping `test_full_simultaneous_rw` alone kills everything, because the random regression catches M1 and M8.

### P3 – Scenario coverage counters
Count how often key FIFO situations actually happened during simulation.
- Scenarios: reset, full, empty, almost_full, write when full (overflow), read when empty (underflow), read and write together when full, read and write together when empty, pointer wraparound.
- **Must not edit the frozen test bench.** Recommended way: a separate `verify/coverage.py` that runs the same frozen suite with waveform dumping on, then counts scenarios from the VCD. It gets its own pinned hash (`verify/coverage.sha256`) and is never shown to the model.
- Run it on the reference RTL and on each run's final RTL. A scenario with a count of 0 is flagged as a gap in P1/P2.
- Done when: the reference RTL shows every scenario with a count above 0, and the counts are identical across two runs of the same RTL.
- Open question for Adrian: whether this is worth the time over P1/P2 if Monday slips. It is the first thing to cut in this list.
- **Result (31 Oct, `make coverage-ref`, `make coverage RUN=<id>`):** `verify/coverage.py` (pinned in `verify/coverage.sha256`) builds its own waves-on simulation of the frozen tests and counts 11 scenarios at each rising edge from a VCD; model RTL is counted inside Docker (image now also carries `spec/interface.json`, read-only). Reference and all three model RTLs: 3253 cycles, every scenario reached (fewest: read+write while full, 10). Counts identical across repeated runs; overflow pulses equal write-when-full events (22) and underflow pulses equal read-when-empty events (141). On a failing design the counts are partial (seeded M1: 532 cycles, because a failing test stops at its first mismatch); the plan says so.

### P4 – Copy changes
- Board hero, page title, README intro and the video script lead with the verification plan and evidence.
- Keep the measured / AI-interpretation labels everywhere.
- Add the two limitations from §2 to the README.
- Respect the engineering handover §8 (no "world model", "Physical AI", speedups or PPA numbers) and the no-names rule.
- **Done 31 Oct:** README intro leads with the plan and evidence; limitations add design breakdown (by a person) and mutation-based coverage (not line/functional, REQ-04/09 untargeted); timing was already listed. Board: kicker "Verification plan", hero lead sentence, traceability labelled as the plan, footer limitations, page description. "Proven by mutation" avoided: mutation testing shows the tests catch planted bugs, nothing more. The video script is not in this repo; it should follow the same order (plan → gaps → AI attempt measured).

## 4. Order and cut line

1. P1 (Mon 2 Nov), since everything else plugs into it.
2. P2 (Mon 2 Nov).
3. P4 (Tue 3 Nov morning).
4. P3 (Tue 3 Nov, only if 1–3 are done).

All four come before UI polish. Benchmark, deploy and the never-cut list in the engineering handover §6 are unchanged.
