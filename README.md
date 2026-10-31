# DaVINCI Silicon

Execution-verified RTL workflow: spec → requirements → frozen tests → mutation proof → AI-generated RTL → real simulation → bounded repair → evidence report.

Built for the Meta Global AI Developer Hackathon 2026 (Startup Track, "Push the Frontier"). Everything in this repo was written during the hackathon (Oct 27 – Nov 4, 2026).

## Status

| Part | State |
| --- | --- |
| Hand-written reference FIFO (`rtl/sync_fifo.v`) | done, 10/10 tests pass |
| Requirements REQ-01..09 (`spec/requirements.json`) | done |
| Frozen cocotb suite + Python golden model (`tests/`) | done |
| Mutation check, 8 seeded bugs (`verify/mutate.py`) | done, 8/8 killed |
| Docker sandbox (`docker/Dockerfile`, `make sandbox`) | written, not yet tested |
| Model client: Meta / Baseten / replay, cost ledger, budget guard (`agent/llm.py`) | done, not yet run live |
| Verified loop with bounded repair, evidence `run.json` (`agent/pipeline.py`) | done, dry-run verified |
| API, UI | next |

## Run

```bash
pip install cocotb==2.1.0     # plus Icarus Verilog (brew install icarus-verilog / apt install iverilog)
make sim                      # run the frozen suite against rtl/sync_fifo.v
make mutate                   # mutation score of the suite
make image && make sandbox    # same run inside the locked-down container
python -m agent.pipeline --run-id dry01 --provider fake          # offline loop, $0
python -m agent.pipeline --run-id demo01 --seed-bug M1           # seeded bug → repair
python -m agent.pipeline --run-id demo01 --provider replay       # replay a recorded run, $0
```

Each run writes `runs/<id>/verdict.json` with RTL hash, suite hash, simulator version, per-test results and runtime.

## Rules the AI must follow

- Tests and the golden model are frozen: the repair agent may only edit RTL; `suite_sha256` is checked every run.
- Every result shown is labelled measured (simulator) or AI interpretation (not verified).
- All attempts are counted, including failures.
