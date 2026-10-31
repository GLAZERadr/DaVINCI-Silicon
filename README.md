# DaVINCI Silicon

A verification plan with evidence for AI-written RTL. Every requirement is traced to frozen tests, mutation testing shows those tests catch planted bugs before any RTL is judged, and every AI attempt is simulated and counted. The model writes Verilog; it never sees, writes or grades the tests.

Each run produces a verification plan (requirement → tests → mutants killed → measured result at attempt 1 and final), the plan's coverage gaps, and a full record of every attempt that replays at $0.

Loop: spec → requirements (human-approved) → frozen tests → mutation proof → AI-generated RTL → real simulation → bounded repair → evidence report → replay.

**Live board:** https://davinci-silicon-fe.vercel.app/ (Evidence and Run Console from the committed evidence bundle; New run and Spec intake need the API).

Until the API is hosted, run it on your machine with `make api` (Docker running) and enter `http://127.0.0.1:8000` under Connection settings on the board's New run or Spec intake page. Chrome asks once to allow the site to reach your local network; allow it. The API only accepts the board's own origins (`CORS` in the Makefile).

Built for the Meta Global AI Developer Hackathon 2026 (Startup Track, "Push the Frontier"). Everything in this repo was written during the hackathon (Oct 27 – Nov 4, 2026).

## Status

| Part | State |
| --- | --- |
| Hand-written reference FIFO (`rtl/sync_fifo.v`) | done, 10/10 tests pass |
| Requirements REQ-01..10 (`spec/requirements.json`) | done |
| Frozen cocotb suite + Python golden model (`tests/`) | done |
| Suite mutation score vs reference RTL, 8 hand-written mutants (`verify/mutate.py`) | 8/8 killed |
| Parameter sweep at 3 other parameter sets, never shown to the model (`verify/run_sweep.py`, `tests_sweep/`) | done; reference passes, hard-coded widths fail |
| Docker sandbox (`docker/Dockerfile`, `make sandbox`, `--sandbox docker`) | done: no network, read-only tests, CPU/mem/pid caps, 120 s timeout |
| Model client: Meta / Baseten / replay, cost ledger, budget guard (`agent/llm.py`) | done; Meta tested live, Baseten not yet |
| Verified loop with bounded repair, evidence `run.json` (`agent/pipeline.py`) | done; 2 live runs + extraction-based live runs |
| HTTP API: runs, SSE progress, replay, mutation, ledger (`api/server.py`) | done |
| Image/PDF spec input → extracted requirements → human approval → RTL (`agent/extract.py`) | done |
| Web UI (`web/`, `make evidence board`): Evidence Board and Run Console as a static site over `evidence/`; New run (live progress) and Spec intake (upload → review → approve → run) against the API | done; API URL from `NEXT_PUBLIC_DAVINCI_API` or the page's Connection settings |
| Coverage gaps: mutation check with each test left out, single-test kills, requirements no mutant targets (`verify/gaps.py`, `make gaps`) | done; directed tests alone miss M1/M8 without `test_full_simultaneous_rw`; REQ-04 and REQ-09 have no mutant |
| Scenario counters: how often the frozen suite reaches full, empty, overflow/underflow cases, simultaneous read+write, wraparound (`verify/coverage.py`, `make coverage`) | done; every scenario reached on the reference and all exported RTLs |
| Waveform and FIFO replay of every attempt: per-cycle trace of the frozen tests with the golden model's expected values, drawn in the Run Console (`verify/trace.py`, `make trace`) | done; measured from the simulator, model RTL traced in Docker |
| Verification plan per run: requirement → tests → mutants → measured result, from stored files only (`verify/plan.py`, `make plan`, `make plan-ref`) | done; in the evidence bundle and downloadable from the board |

## Run

```bash
pip install -r requirements.txt   # plus Icarus Verilog (brew install icarus-verilog / apt install iverilog)
make sim                      # run the frozen suite against rtl/sync_fifo.v
make mutate                   # mutation score of the suite
make weak-demo                # weakened suite lets mutants survive; full suite kills them
make image && make sandbox    # same run inside the locked-down container
python -m agent.pipeline --run-id dry01 --provider fake          # offline loop, $0
python -m agent.pipeline --run-id demo01 --seed-bug M1           # seeded bug → repair
python -m agent.pipeline --run-id sbx01 --sandbox docker        # simulate inside the sandbox
make api                                                         # HTTP API on :8000
make gaps                                                        # where the test plan is thin (37 s, local)
make coverage RUN=live01-replay-7c96                             # scenario counts on a run's final RTL (in Docker)
make trace RUN=live02-m1                                         # waveform/FIFO trace of each attempt (in Docker)
make plan RUN=live01                                             # runs/live01/verification_plan.{md,json}, $0, no simulation
make plan-ref                                                    # same for the reference RTL (simulates it locally)
make evidence                                                    # export live runs + replays + their plans to evidence/
make board                                                       # build the Evidence Board to web/out
python -m agent.extract spec/fixtures/sf16_datasheet.pdf         # spec page → requirements for approval
python -m agent.extract --remap <xid>                            # re-run only the mapping step
python -m agent.extract --approve <xid> --by "Name"              # approve; then run with
#   --requirements runs/_extract/<xid>/approved.json --spec runs/_extract/<xid>/interface_spec.md
python -m agent.pipeline --run-id demo01 --provider replay       # replay a recorded run, $0
```

Each run writes `runs/<id>/run.json` (every attempt, cost, status) plus, per attempt, `attempt_<n>/sim/verdict.json` (RTL hash, suite hash, simulator, per-test results) and, on a visible pass, `attempt_<n>/sweep/sweep.json`.

## How a design is judged

| Gate | Check | Tool |
| --- | --- | --- |
| G1 static | no `$` or compiler directive except `` `timescale ``; no `initial` or `#` delays; ports match `spec/interface.json`; compiles as Verilog-2001 | regex, `iverilog -g2001 -Wall` |
| G2 visible | 10 frozen tests, golden model compared every cycle, default parameters | Icarus + cocotb |
| G3 sweep | the same golden model at WIDTH/DEPTH/AF_THRESH = 8/12/9, 1/2/1, 32/32/32; results never shown to the model | Icarus + cocotb |

Run statuses: `pass` (G1–G3), `escaped` (passed the visible suite, failed the sweep), `needs_engineer` (repairs exhausted; failing tests handed over), `no_progress` (the same design twice), `aborted`, `not_verifiable` (spec or requirements the suite cannot judge; no model call). Attempt statuses add `rejected` and `truncated` (reply cut off at the token limit).

## Limitations

- **Design breakdown is done by a person.** The requirements and the port/parameter interface (`spec/requirements.json`, `spec/interface.json`) are written and approved by a person, or extracted from a spec page and then approved. DaVINCI does not derive a microarchitecture from a spec.
- **Coverage means mutation-based plan coverage.** It shows which of 8 hand-written bugs the tests catch and where the plan is thin (`make gaps`); it is not line, toggle or functional coverage. REQ-04 and REQ-09 have no mutant yet.
- **The default spec contains the reference equations.** `spec/fifo_spec.md` states `do_write = wr_en && (!full || rd_en)` and the flag equations, so first-pass success on it measures spec-conformant transcription, not design from an ambiguous spec. A prose-only spec arm is planned.
- **One block, one simulator.** A sync FIFO on Icarus Verilog; not sign-off evidence for a commercial flow.
- **The mutation score describes the test suite**, measured against the hand-written reference RTL with 8 hand-written mutants. It is not a property of any generated RTL.
- **Same author for both oracles.** The frozen suite and the sweep share `tests/golden_model.py`; a misreading of the spec shared by the model and the reference would pass both.
- **Replay re-simulates recorded model output.** "Re-simulation reproducibility" checks the pipeline and simulator, not that the model would answer the same way again.
- **No synthesis, timing, area or power results.** None are claimed.
- **Small N.** Live results so far are individual runs, not rates.

## Rules the AI must follow

- Tests and the golden model are frozen: the repair agent may only edit RTL; `suite_sha256` is checked every run.
- Every result shown is labelled measured (simulator) or AI interpretation (not verified).
- All attempts are counted, including failures.
- Model-written RTL is only simulated inside the Docker sandbox; live model calls through the API need `DAVINCI_API_TOKEN`.

Architecture review and decisions: `docs/architecture/`.
