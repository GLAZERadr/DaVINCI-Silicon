# 01 — Multi-domain review

Eight independent, read-only reviewers audited the repository at `f41fb60` on 31 Oct 2026, each from a written brief. For this first run they were executed as read-only planning agents loading those briefs. The orchestrator then re-checked the load-bearing claims by hand. Each claim's status is given as **Orchestrator-verified** (re-run or re-read by the main session), **Reviewer-verified** (cited to file and line, not re-run) or **Assumption**.

Agreement between reviewers is not treated as validation. Where they agree, it is noted, but the evidence column is what counts.

## 1. Orchestrator-verified facts

| # | Fact | How it was checked |
| --- | --- | --- |
| V1 | **The response cache no longer holds the live model replies.** `runs/_cache/<hash>.json` for live01 (`c6e7ce2c…`) and live02-m1 (`73e9537f…`) now contain `"model": "fake-reference"`. The original replies survive only in `runs/live*/attempt_*/response.md`. | Compared each cache entry to the recorded `response.md`: both differ. Cause: `agent/llm.py` writes the cache for every non-replay provider, and `request_hash` ignores the provider. Fake runs with the default prompt overwrote the live entries. |
| V2 | **The FORBIDDEN regex can be bypassed to write arbitrary files.** `` `define FO(x) $fo``x `` followed by `` `FO(pen)(path,"w") `` and `$fwriteh(fd, …)` passes the regex, compiles under Icarus 13 and writes the file. `$fwriteh`, `$fdisplayb` and `$fstrobeo` all pass the regex. `$system` is not implemented by Icarus, so the same trick gives no shell. | Built the probe in the scratchpad; the target file was created. Docker blocks writes to `tests/` and `verify/`, but the default `local` backend does not. |
| V3 | **SystemVerilog is accepted even though the spec says Verilog-2001.** The cocotb Icarus runner passes `-g2012`. | `cocotb_tools/runner.py:1000` |
| V4 | **Model RTL that passes can still be wasteful.** live01 declares `reg [31:0] wptr, rptr`, where 4 bits suffice. | `runs/live01/attempt_1/sync_fifo.v:22-23` |
| V5 | **The spec contains the reference equations.** `do_write = wr_en && (!full \|\| rd_en)` appears at `spec/fifo_spec.md:52`. The live02-m1 repair diagnosis quotes it. | Read both. |
| V6 | **Yosys and Verilator are not installed.** Any synthesis or lint gate needs a new tool, except Icarus' own `-g2001 -Wall`. | `which yosys verilator` |

## 2. Critical and high findings, by theme

### A. The evidence does not yet support a capability claim (all 8 reviewers)

| Finding | Severity | Status | Raised by |
| --- | --- | --- | --- |
| The spec gives the implementation away, so first-pass success and the M1 repair measure transcription. | Critical/High | Orchestrator-verified (V5) | EDA, AI, verification, workflow, red team, data |
| Only one parameter set is tested; RTL with hard-coded widths passes. | High | Reviewer-verified (`tests/test_sync_fifo.py:13`, no `parameters=` in `verify/run_suite.py`) | EDA, verification, world model, red team |
| No holdout: up to three repairs see the same suite they are judged on. | High | Reviewer-verified | verification |
| No synthesis or lint gate; `initial`, `#` delays and SV syntax pass. | High | Orchestrator-verified (V3) | EDA, verification, red team |
| The "mutation score" describes the suite against the reference RTL, not the generated RTL. Its 8 mutants were written by the same author as the tests. | High | Reviewer-verified (`verify/mutate.py:27-28`) | verification, EDA, red team, workflow |
| N = 1 live run per configuration; nothing supports a rate. | Medium | Orchestrator-verified | AI, red team |
| "Replay reproducibility" only re-simulates recorded text, so it tests simulator determinism, not model reproducibility. | Medium | Reviewer-verified (`agent/pipeline.py:341-358`) | AI, verification, red team |

### B. Defects in what exists (security and integrity)

| Finding | Severity | Status | Raised by |
| --- | --- | --- | --- |
| Replay of both live runs is broken by cache overwrite. | **Critical** | Orchestrator-verified (V1) | data, verification, red team |
| Regex denylist bypass → arbitrary file write on the `local` backend. | **Critical** | Orchestrator-verified (V2) | platform, red team (hypothesised), verification |
| `local` is the default sandbox and the API lets clients choose it. The subprocess inherits API keys. | Critical | Reviewer-verified (`api/server.py:62`, `agent/pipeline.py:117-119`) | platform, red team |
| The API fails open when `DAVINCI_API_TOKEN` is unset, so the $120 budget sits behind an unauthenticated POST. The token comparison is not constant-time. | High | Reviewer-verified (`api/server.py:131-134`) | platform, red team |
| The pinned suite hash excludes `verify/run_suite.py`, which decides pass or fail, and `verify/mutants.json`. | High | Reviewer-verified (`verify/run_suite.py:24-28`) | data, platform |
| The sandbox writes the `verdict.json` the host trusts, into a bind mount. `attempt_file` follows symlinks when serving. | High (Critical if public) | Reviewer-verified; exploit not demonstrated | platform |
| The worker thread has no try/except, so one bad job stalls the queue while `/health` still reports ok. | High | Reviewer-verified (`api/server.py:89-107`) | platform |
| After a rejected attempt, `prev_rtl` is overwritten with the rejected output (possibly `None`), so the next repair loses the last simulated RTL. | Medium | Orchestrator-verified (read `agent/pipeline.py`) | AI |
| `finish_reason` is recorded but never checked, and about 90 % of live01's output tokens were hidden reasoning against an 8,000 cap. A truncated reply would be miscounted as "rejected". | High | Reviewer-verified (token vs byte counts) | AI |

### C. Traceability gaps

| Finding | Severity | Raised by |
| --- | --- | --- |
| `mutation.json` and `weak_demo.json` carry no suite hash, so the score cannot be tied to a run. | High | data |
| `run.json` omits git commit, reference RTL hash, mutants hash, runner hash, prompt template hash, options and toolchain. | High | data |
| The requirement → test mapping is never checked. The API accepts any spec but always grades with the FIFO suite. | High | data, AI, EDA, red team |
| There is no approval record; "human-approved" is not a stored fact yet. Approval is being built in the parallel session. | Medium | data |
| No schema versions, and formats already drift (`live02-m1` has no `sandbox` key). | Medium | data |
| Evidence lives only in git-ignored `runs/` on one laptop. | Medium | data, platform |

### D. Strategy and market

| Finding | Severity | Status | Raised by |
| --- | --- | --- | --- |
| "Generate → simulate → repair" is a crowded category: Synopsys AgentEngineer, Siemens Questa One Agentic Toolkit, Cadence ChipStack, ChipAgents, plus academic AutoChip and MAGE. | High | Reviewer-verified with URLs (Cadence and ChipAgents pages returned 403; secondary sources) | workflow |
| Verification, not RTL writing, is where engineering time goes (49 % of design-engineer time, Wilson 2022). | High | Reviewer-verified (survey, not DaVINCI users) | workflow |
| DaVINCI assumes the expensive input already exists: a qualified testbench and golden model. For the FIFO they total 218 lines against 61 lines of RTL. | Critical | Reviewer-verified (line counts); generalisation is an assumption | workflow, red team |
| Sending specs and RTL to a hosted API blocks industrial customers with IP or NDA constraints. | High | Assumption (no customer data) | workflow, EDA, data |
| Mutation-based testbench qualification has prior art (Synopsys Certitude). | Medium | Reviewer-verified from a search summary | workflow |
| Public benchmarks (CVDP: ≤34 % pass@1) show hard RTL tasks are unsolved; a FIFO is not one of them. | Medium | Reviewer-verified (arXiv 2506.14074) | workflow |

### E. World model and "Physical AI"

**Unanimous conclusion, with evidence:** the repo has no learned world model and needs none for functional RTL.
- **The exact dynamics model already exists.** `tests/golden_model.py` is a deterministic transition function, compared on every cycle.
- **Prediction can't beat simulation here.** Simulation costs 0.23–0.39 s per attempt against 6–27 s per model call (`runs/live*/run.json`), so a learned predictor saves nothing and adds error.
- **The only plausible future surrogate has no data.** That would be PPA estimation after synthesis, and there is no synthesis data at all.
- **Recommendation:** defer. Revisit only when synthesis or STA time is far above model time and there are about 200 logged synthesis results across 3 or more blocks.

## 3. Disagreements between reviewers, and how they were resolved

| Topic | Positions | Resolution | Basis |
| --- | --- | --- | --- |
| Parameter sweep timing | Verification: P1 now. EDA and world model: after freeze, because the frozen suite must not change. | Add the sweep as a **separate, versioned holdout suite** (new files, own hash). The frozen files stay untouched. | Both concerns hold. Separate files satisfy the "never modify frozen tests" rule and still close the gap. The red team challenges this in its second pass. |
| Synthesis/lint gate vs "one simulator" scope rule | EDA and verification: add it. The engineering handover: one simulator. | `iverilog -g2001 -Wall` compile-only needs no new tool: do it. Adding Yosys is Adrian's call. | A lint pass is not a second simulator. A new tool is a scope change. |
| Benchmark size | AI: N ≥ 30 per condition. The engineering handover: N ≥ 10. Red team: split by condition. | N ≥ 10 per headline cell, conditions split, Wilson intervals. | Cost is about $0.03 per run, so money doesn't bind; wall-clock time and the deadline do. |
| What the product is | the engineering handover: spec → RTL generation. Workflow and red team: the trust/evidence layer is the product; generation is commodity. | Hackathon: keep generation (judged on Meta model use), but lead the demo with the trust layer and narrow the claims. Post-hackathon MVP: trust gate for RTL from any source. | Market evidence (crowded generation category) and cost evidence (verification dominates). Not settled without user interviews. |
| Cache vs self-contained runs | Data: replay from the run directory. Red team: per-run, per-call keys. Verification: content-addressed by response. | Replay reads `runs/<src>/attempt_n/response.md`. Any cache is content-addressed and never overwritten. The fake provider never caches. | All three proposals fix V1; this one adds no new storage. |
| Diagnosis checking | AI: structured JSON plus signal check. Verification: consistency from measured outcomes. World model: localisation rate on seeded runs. | All three are measured, cheap and complementary: P2, after the P0/P1 items. | No conflict, only priority. |

## 4. Points no reviewer could settle

- Muse Spark's first-pass rate on a prose-only spec (needs about 10 live runs, about $0.30).
- Whether the live RTLs pass at other parameter sets (needs one sweep run).
- Whether a background process inside Docker could race `results.xml` (needs a probe with process spawn).
- Whether Muse Spark counts reasoning tokens in `completion_tokens`, and what `reasoning_effort` changes.
- Meta and Baseten data-retention and training terms for Standard mode.
- Whether RTL, DV or CAD engineers would adopt a trust gate, or pay for one: **zero user interviews exist**.
- How much engineer time a golden model and suite cost compared with the RTL, on a block other than the FIFO.
