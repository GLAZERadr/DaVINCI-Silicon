# 00 — Current state assessment

Snapshot of the repository at commit `5cc5c23` (31 Oct 2026). Image/PDF spec input was being built in a parallel session at the time and is not counted here. Every statement below is either checked against the code or a recorded run, or labelled otherwise.

## 1. What DaVINCI is today, in one paragraph

A verification-first loop for **one digital block** (a parameterised synchronous FIFO) on **one simulator** (Icarus Verilog through cocotb). A language model (Meta Muse Spark 1.3) writes Verilog from a written spec and an approved requirements list. A frozen, hash-pinned test suite with a cycle-accurate Python golden model judges it. On failure the model gets the simulator's measured failures and tries again, up to three repairs. Every attempt, model call and cost is recorded, and any run can be replayed at $0. There is no physical simulation, no synthesis or layout, no learned predictive model and no UI yet.

## 2. Inventory

| Layer | Component | Files | State | Evidence |
| --- | --- | --- | --- | --- |
| Spec | Written spec + interface | `spec/fifo_spec.md` | done | file |
| Spec | Requirements REQ-01..09 → tests | `spec/requirements.json` | done | file |
| Reference | Hand-written RTL | `rtl/sync_fifo.v` | 10/10 | `make sim` |
| Verification | Frozen cocotb suite (10 tests, 3000-cycle seeded random) | `tests/test_sync_fifo.py` (seed at :160) | frozen | `verify/suite.sha256` |
| Verification | Golden model (cycle-accurate) | `tests/golden_model.py` | frozen | same hash |
| Verification | Suite runner → `verdict.json` | `verify/run_suite.py:41` | done | runs/*/sim/verdict.json |
| Verification | Mutation check, 8 mutants | `verify/mutate.py:23`, `verify/mutants.json` | 8/8 killed | `runs/mutation/mutation.json` |
| Verification | Weak-test demo | `verify/mutate.py:50` | weak 6/8 → restored 8/8 | `runs/weak_demo/weak_demo.json` |
| AI | Model client: meta / baseten / replay / fake; ledger; budget guard; cache | `agent/llm.py:28`, `:121`, `:215` | done; only Meta tested live | `runs/_ledger.jsonl` |
| AI | Verified loop with bounded repair | `agent/pipeline.py:187` | done | `runs/live01`, `runs/live02-m1` |
| Safety | Pre-sim filter on generated RTL | `agent/pipeline.py:33` (FORBIDDEN regex) | done | dry-run rejection test |
| Safety | Suite hash before / after each sim / after run | `agent/pipeline.py:62` | done | |
| Execution | Local subprocess backend | `agent/pipeline.py:108` | done | |
| Execution | Docker sandbox (no net, caps dropped, ro root, pid/mem/CPU caps, 120 s) | `docker/Dockerfile`, `agent/pipeline.py:42`, `Makefile:19` | verified on macOS arm64 | probes in session, 31 Oct |
| Execution | Modal Sandbox backend | — | **not started** | |
| API | FastAPI: runs, SSE, replay, files, mutation, ledger, health | `api/server.py` | done, tested at $0 | |
| UI | Evidence Board + Run Console | — | **not started** | |
| Input | Image/PDF spec → requirements → human approval | — | in progress elsewhere | |
| Repair on open weights | Baseten Muse Spark Open | `agent/llm.py:28` | **not run live** | |
| Benchmark | ≥10 live runs → metrics table | — | **not started** | |

Stack: Python 3.12/3.13, cocotb 2.1.0, Icarus Verilog 12 (container) / 13 (dev Mac), FastAPI 0.162, uvicorn 0.54, Docker. No database, no message queue, no frontend framework yet. About 1,100 lines of Python excluding tests.

## 3. Verified capabilities (measured)

| Claim | Evidence |
| --- | --- |
| The reference RTL passes the frozen suite | `make sim`: 10/10 |
| The suite kills all 8 hand-written mutants | `make mutate`: 8/8 |
| Dropping the REQ-06 tests lets M1 and M8 survive; the full suite kills them | `make weak-demo`: 6/8 → 8/8 |
| Muse Spark 1.3 wrote a passing FIFO on its first attempt, once | `runs/live01/run.json`: 1 attempt, 1,455 in / 5,947 out tokens, $0.027, 27.7 s |
| Muse Spark 1.3 repaired a seeded M1 bug in one step, once | `runs/live02-m1/run.json`: 8/10 → 10/10, $0.008, 7.1 s |
| Replay reproduces both live runs, locally and in Docker | `runs/*-replay*/run.json` → `replay_check.reproduced: true` |
| Local and Docker simulators give identical per-test verdicts on those runs | session comparison 31 Oct, Icarus 13 vs 12 |
| Sandbox blocks network and writes to tests, caps pids, stops a runtime infinite loop at 120 s | session probes 31 Oct |

**N = 1 per configuration.** None of these numbers is a rate. Nothing here supports a success-rate, speed-up or productivity claim yet.

## 4. Gaps and conflicts found during discovery

1. **The vision and the code are about different things.** The stated ambition is "Physical AI and World Models" for engineering design. The code is a test-driven RTL generation loop for digital logic, with no physical model. `CLAUDE.md` §8 even forbids "world model", "Physical AI" and "digital twin" in README and UI copy. This review has to settle whether the framing helps or hurts.
2. **The spec gives away the key logic.** `spec/fifo_spec.md:52` states `do_write = wr_en && (!full || rd_en)`, the exact line mutant M1 breaks. The model's diagnosis in `live02-m1` quotes it. First-pass success on this spec says little about capability on underspecified designs.
3. **Default parameters only.** The suite instantiates WIDTH=8, DEPTH=16, AF_THRESH=14. RTL that hard-codes those values would pass.
4. **No synthesis or lint gate.** "Passes simulation" is the only correctness signal. Unsynthesisable or simulation-only constructs are caught only if Icarus rejects them.
5. **Mutation set is small and hand-written** (8 mutants, one per requirement). It measures the suite against bugs we thought of, not against bugs a model makes.
6. **Single-tenant, local state.** Runs, ledger and queue live under `runs/` on one machine, and the API's queue is in memory. Fine for a demo, not for anything shared.
7. **The sandbox can write its own verdict directory.** `/work/out` must be writable. Only the FORBIDDEN regex stops generated RTL from writing a forged `verdict.json`.
8. **Hosted path missing.** Modal backend, deployment and UI are not built. The judges' "live product" does not exist yet.

## 5. Constraints that bound any recommendation

- Deadline: submit 4 Nov 2026 21:00 WIB, feature freeze 3 Nov 23:59 WIB, about 3.5 days from this snapshot.
- Budget: $150 model credit, hard stop $120. Spend so far is about $0.035 (`runs/_ledger.jsonl`).
- Scope rule in `CLAUDE.md` §2: one block, one simulator, no UART, OpenROAD, multi-agent frameworks or digital twin.
- Judging: impact 30 %, use of Meta AI tooling 25 %, technical depth 20 %, demo 25 %.
- Team: one lead engineer plus AI agents.

## 6. Missing information

- No user interviews, design-partner feedback or market evidence exists in the repo.
- No data on how the model behaves across repeated runs, other blocks or other prompts.
- No synthesis, timing or area numbers of any kind.
- Baseten and Modal credit approval is unknown (`CLAUDE.md` §9).
