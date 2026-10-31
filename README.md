# DaVINCI Silicon

Execution-verified RTL workflow: spec → requirements → frozen tests → mutation proof → AI-generated RTL → real simulation → bounded repair → evidence report.

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
| Evidence Board: static Next.js site over the committed `evidence/` bundle (`web/`, `make evidence board`) | done; Run Console deferred |

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
make evidence                                                    # export live runs + replays to evidence/
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
