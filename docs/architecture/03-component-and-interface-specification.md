# 03 — Component and interface specification

Contracts for the target architecture in `02`. "Exists" means present at `5cc5c23`; "change" lists the deltas the review calls for. One process, files on disk. These are module and file contracts, not service boundaries.

## 1. Components

### C1. Pipeline orchestrator: `agent/pipeline.py` (exists)
- **Purpose:** run one verified-generation run end to end, deterministically.
- **Inputs:** run id, providers per step, spec path, requirements path (+ approval record), seed bug, sandbox backend, max repairs (≤3).
- **Outputs:** `runs/<id>/` (C6 contract), exit code 0 on pass.
- **Responsibilities:** check the suite hash before the run, after each simulation and after the run; call C2 for model text; call C3 then C4 for verdicts; decide stop conditions; record every attempt.
- **Depends on:** C2, C3, C4, C6.
- **Failure scenarios and handling:**
  - Model error or budget refusal → `aborted`.
  - Truncated reply → `truncated` *(change)*.
  - No progress → `no_progress` *(change)*.
  - Repairs exhausted → `needs_engineer` *(change; today `fail`)*.
  - Suite hash mismatch → hard abort.
- **Changes:**
  - Keep the last *simulated* RTL in the repair prompt after a rejection (bug: `prev_rtl` is overwritten).
  - Check `finish_reason`.
  - Raise `max_tokens` to ≥16k and record `reasoning_effort`.
  - Add `git_commit` and toolchain versions to run.json.
  - Refuse `--sandbox local` for live providers.
- **Validation:** fake-provider tests for each stop state (existing pattern from the dry runs).

### C2. Model client: `agent/llm.py` (exists)
- **Purpose:** one `call()` for every provider; ledger; budget guard.
- **Inputs:** messages, provider, step, run id, options.
- **Outputs:** `Reply` (text, tokens, cost, model, `finish_reason`), plus a ledger line for every call, including failures and refusals.
- **Failure scenarios:** missing key or price → refused and ledgered; HTTP error → `LLMError`; replay source missing → `LLMError`.
- **Changes:**
  - Replay reads `runs/<source>/attempt_n/response.md` in `calls.jsonl` order (fixes V1).
  - The fake provider never writes shared state.
  - Any cache is keyed by `sha256(provider|model|request)` and refuses to overwrite.
  - Record `response_sha256` in `calls.jsonl`.
  - *Post:* file lock around guard plus ledger append; `data_use_mode` per call.
- **Validation:** fake → live-shaped → fake → replay of the live-shaped run reproduces its RTL hashes.

### C3. Static gate G1: in `agent/pipeline.py` `validate()` (exists as a regex; change)
- **Purpose:** reject RTL that should never reach a simulator.
- **Input:** RTL text. **Output:** `None` or a rejection reason (measured).
- **Rules (target):**
  1. No `$` anywhere.
  2. No backtick except `` `timescale ``.
  3. One `module sync_fifo`, with ports and widths matching the spec interface.
  4. `iverilog -g2001 -Wall` compile-only succeeds; warnings recorded.
  5. ≤64 KB.
- **Why this shape:** rules 1–2 close the confirmed bypass (V2) in two lines. A full allowlist parser is days of risky work (red-team pass 2). The reference and both live RTLs contain no `$` and no backtick except `` `timescale `` (checked).
- **Failure scenarios:** a legitimate future block needs `$clog2`. Extend with an explicit, reviewed allowlist entry at that point.
- **Validation:** fixtures for `$fwriteh`, pasted `` $fo``pen ``, `` `include ``, `always_ff`, `initial` → all rejected; the reference passes.

### C4. Simulator backend: `simulate()` + `verify/run_suite.py` (exists)
- **Purpose:** produce a measured verdict.
- **Input:** RTL path, output dir, backend (`docker`; `local` only for replay and fake), optional suite selector (`frozen` | `sweep`).
- **Output:** `verdict.json` (C6).
- **Responsibilities:** mount the RTL read-only; enforce timeout and caps; check the test count and names against the expected set *(change)*.
- **Failure scenarios:**
  - Compile error → `compile_error`.
  - Timeout → `timeout`.
  - No verdict → `sim_error`.
  - Verdict suite hash ≠ pinned → abort (stale image).
- **Change (post):** return the verdict on stdout from a tmpfs inside the sandbox rather than via a writable bind mount; reject symlinks.
- **Validation:** local vs Docker per-test equality on recorded runs (done for live01 and live02-m1).

### C5. Parameter sweep suite G3: new `tests_sweep/` (build)
- **Purpose:** catch RTL that only works at the default parameters.
- **Content:** the same golden model, instantiated at ≥3 parameter sets with consistent CW, for example (8,16,14,5), (8,12,9,4), (1,2,1,2), via cocotb runner `parameters=`.
- **Hash:** its own pinned hash in `verify/sweep.sha256`; it never changes the frozen suite.
- **Output:** sweep results are never put in the model's prompt. Wording: "not shown to the model". Not "hidden": the repo is public.
- **Known limit:** same author and golden model as the frozen suite, so a shared misreading of the spec is invisible to both.
- **Validation:** the reference passes all sets; a variant with hard-coded `[3:0]` pointers fails.

### C6. Evidence store: `runs/` (exists) + `evidence/` (build)
See the data contracts in §2.

### C7. Mutation check: `verify/mutate.py` (exists)
- **Purpose:** measure suite adequacy against the reference (8 hand-written mutants) and stage the weak-test demo.
- **Change:** write `suite_sha256`, `ref_rtl_sha256`, `mutants_sha256`, `simulator` and `created` into `mutation.json` and `weak_demo.json`.
- **Label everywhere:** "Suite mutation score vs reference (8 hand-written mutants)".
- **Never presented as:** a property of generated RTL.

### C8. HTTP API: `api/server.py` (exists)
- **Purpose:** operator interface for queuing runs; read endpoints for the board.
- **Changes (P0):**
  - Refuse live-provider runs when `DAVINCI_API_TOKEN` is unset.
  - Use `secrets.compare_digest`.
  - Remove the client-selectable `sandbox`; the server decides.
- **Changes (P1):**
  - Worker try/except/finally that always records `error`.
  - `/health` reports worker liveness.
  - Reject specs whose interface or parameters don't match a frozen suite, as `not_verifiable`.
- **Public surface for the hackathon:** none required if the board is static. If the API is exposed: GET endpoints plus rate-limited replay only.

### C9. Requirement extraction + approval (in progress in a parallel session)
- **Input:** an image or PDF (rasterised to PNG); provider `meta`.
- **Output:** `extracted.json`, where each requirement carries `{id, text, source_page, source_quote, confidence}`, labelled AI interpretation. Then `approved.json` with `{requirements_sha256, approved_by, approved_at, source_sha256, extraction_call}`.
- **Guards:**
  - Deterministic check that each `source_quote` appears in the PDF text layer, where one exists.
  - Interface and parameter guard against the frozen suite.
  - No run without an approval whose hash matches.
- **Known limit:** the guard is syntactic. It cannot tell whether extracted behaviour matches what the tests check.

### C10. Evidence Board (build, static)
- **Input:** `evidence/` bundle.
- **Shows:**
  - Verdict hero.
  - Mutation score (only when the suite hash matches).
  - Attempts to green, time to green, cost.
  - Traceability REQ → test → mutants killed → attempt 1 → final.
  - "What changed and why", with the AI box dashed and the measured box solid.
  - Reproduce-it commands; replay.
- **Never shows:** numbers that aren't in the bundle.

## 2. Data contracts

All files are JSON or JSONL and UTF-8. Paths are relative to the repo root. Adding a `"schema"` field to each is a post-hackathon item; field names below match the current code.

### run.json (`runs/<id>/run.json`)
| Field | Type | Notes |
| --- | --- | --- |
| `run_id`, `started`, `finished` | str | |
| `providers` | `{generate, repair}` | |
| `seed_bug` | str \| null | |
| `replayed_from` | str \| null | |
| `sandbox` | `{backend, image, image_id}` | |
| `suite_sha256`, `spec_sha256`, `requirements_sha256` | str | the suite hash will be extended to cover runner + mutants |
| `git_commit`, `toolchain` | str, obj | *change* |
| `approval` | obj \| null | *change*: copied from `approved.json` |
| `attempts[]` | Attempt | see below |
| `status` | `pass \| fail \| aborted \| escaped \| needs_engineer \| no_progress \| not_verifiable` | *extended* |
| `attempts_total`, `attempts_to_green`, `first_pass`, `time_to_green_s`, `wall_seconds`, `cost_usd`, `tokens` | | |
| `replay_check` | `{reproduced, attempts[]}` | rename the metric to "re-simulation reproducibility"; `reproduced` requires `request_match` not false |

**Attempt:**
- `{n, source: model|seeded, provider, model, status, tokens_in, tokens_out, cost_usd, model_seconds, finish_reason, rtl_sha256, diff_vs_prev, measured{label:"measured", status, passed, total, failed[], simulator, sim_seconds, suite_sha256, sandbox}, sweep{…}, ai_interpretation{label, diagnosis}}`
- `status` ∈ `pass | fail | compile_error | sim_error | timeout | rejected | truncated | aborted`

### verdict.json (`attempt_n/sim/verdict.json`)
`{rtl (relative path: change), rtl_sha256, suite_sha256, simulator, tests[{name, passed, message}], passed, total, status, seconds, tests_dropped?, sandbox}`

### calls.jsonl
One line per model call: `{step, attempt, ok, error, provider, model, request_sha256, response_sha256 (change), tokens_in, tokens_out, cost_usd, seconds, extra}`

### events.jsonl
One line per event: `{t, type, …}`. Types: `run_started, seeded, model_call, diagnosis, rejected, simulating, verdict, aborted, run_finished` (+ `truncated, no_progress` as changes). This is the SSE payload.

### _ledger.jsonl
Every call, including refused ones: `{ts, run_id, step, provider, request_sha256, status: ok|error|refused_budget, model?, tokens_in?, tokens_out?, cost_usd, seconds?, error?}`

### mutation.json / weak_demo.json
Current fields, plus `suite_sha256, ref_rtl_sha256, mutants_sha256, simulator, created` *(change)*.

### requirements.json
`{block, params{WIDTH, DEPTH, AF_THRESH}, requirements[{id, text, tests[]}]}`. *Change:* at run start, check every name in `tests[]` against `run_suite.all_tests()`, and check `block`/`params` against the suite.

### evidence/ bundle (build)
`evidence/<run_id>/{run.json, calls.jsonl, events.jsonl, attempt_n/{prompt.json, response.md, sync_fifo.v, sim/verdict.json}}`, plus `evidence/mutation.json`, `evidence/weak_demo.json`, `evidence/ledger.jsonl` and `evidence/MANIFEST.sha256`. No `sim_build/`, no absolute paths, no secrets.

## 3. Interfaces between subsystems

| From → to | Interface | Contract |
| --- | --- | --- |
| UI (approval) → pipeline | `approved.json` | Hash must equal `run.requirements_sha256` |
| Pipeline → model client | `llm.call(messages, provider, step, run_id, **opts)` | Returns `Reply` or raises; always ledgered |
| Pipeline → G1 | `validate(rtl) -> reason \| None` | Pure function |
| Pipeline → simulator | `simulate(rtl_path, out, backend, suite)` | Returns a verdict dict; the file is written by the host *(post change)* |
| Pipeline → store | run directory | Write-once per attempt; `run.json` written at the end |
| Store → board | `evidence/` bundle | Read-only, hashed |
| API → pipeline | subprocess argv | One job at a time; job lifecycle in `runs/_api/jobs.jsonl` |

## 4. Integration requirements

| Integration | Need | Status |
| --- | --- | --- |
| Meta Model API | key, price env vars | working |
| Baseten | key, price env vars, credit approval | key present; price unset; credits unknown |
| Modal | token, credit approval | token present; credits unknown; deferred |
| Icarus | 12 in image, 13 local | pin one version for the benchmark |
| Yosys / Verilator | not installed | needs a scope decision before adding to the image |
