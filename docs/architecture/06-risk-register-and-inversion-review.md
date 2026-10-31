# 06 — Risk register and inversion review

> **Update, 31 Oct (after the review):** the P0 items are fixed and tested. R1 (replay reads each run's own `response.md`; the cache archives live replies by content and never overwrites), R2 (no `$`, no directive except `` `timescale ``; model RTL refused outside Docker; secrets removed from the local env), R5 (fail-closed token with `compare_digest`; no client-chosen sandbox), and the pinned hash now covers `verify/run_suite.py` and `verify/mutants.json`. live01 and live02-m1 replay with `reproduced: true` again. `request_match` is false because the system prompt changed, which is the intended drift flag.

Inversion question for each decision: *what would make this fail?* Likelihood (L) and impact (I) are rated H/M/L. Status reflects 31 Oct 2026.

## 1. Risk register

| ID | Risk | L | I | Evidence | Mitigation | Owner / when |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | **Demo replay serves fake RTL** | H (already true) | H | V1: both live cache entries hold `fake-reference` | ADR-004; restore from `response.md`; replay-integrity test | P0, before any demo work |
| R2 | **Host file write by model RTL** | M (needs injection or odd output) | H | V2: pasted `$fopen` + `$fwriteh` wrote a file; `local` is the default | ADR-006 + ADR-010; docker-only for live providers | P0 |
| R3 | **The trust gate relocates the oracle cost rather than removing it.** Someone still writes each block's tests and golden model (218 lines vs 61 lines of RTL for the FIFO). | H | H | line counts; red team passes 1–2 | Treat the pivot as a hypothesis; V-2 (block from outside the team); V-4 (independently authored AI oracles) | Post |
| R4 | **Judges discount the result** because the spec contains the answer | H | H | V5; live02-m1 diagnosis quotes the spec | Arm B with an independently written prose spec; state the caveat on the board and in the README | P1 |
| R5 | **Budget theft via open API** | M if exposed | M | `api/server.py:131-134` fails open | ADR-010; static public surface (ADR-009) | P0 |
| R6 | **Escapes at other parameters** (hard-coded widths pass) | M | M | `tests/test_sync_fifo.py:13` | G3 sweep (ADR-007) | P1 |
| R7 | **Truncated replies miscounted as model failures** | M | M | live01: 5,947 output tokens, ~2 KB visible, cap 8,000 | `max_tokens` ≥ 16k, `truncated` status | P1 |
| R8 | **Scope overrun before freeze** (four products at once) | H | H | red team pass 2: 20+ build items in the first draft | the cut list in §4; ADR-009, ADR-011 | Now |
| R9 | **Incumbents already ship the loop and bundle evidence features** | H | H | Synopsys, Siemens, Cadence, ChipAgents (URLs in `01`) | Differentiate on independence and evidence; interviews before building the product | Post |
| R10 | **IP blocks industrial adoption** (hosted model API) | M | H | assumption; RTL is closely guarded | academic and open-hardware users first; pluggable or local model | Post |
| R11 | **Shared misreading in the oracle** (golden model and reference by the same author) | M | M | `spec/fifo_spec.md` rebuilt from RTL and golden model | formal properties from the prose spec (post); independent authors | Post |
| R12 | **Mutation score misread as a property of generated RTL** | H | M | `verify/mutate.py:27-28` | label, bind to suite hash (C7) | P1 |
| R13 | **Evidence lost** (git-ignored `runs/` on one laptop) | L | H | `.gitignore` | committed `evidence/` bundle with manifest | P1 |
| R14 | **Worker thread dies silently in the demo** | L | M | `api/server.py:89-107` | try/except/finally; liveness in `/health`; static board removes the dependency | P1 |
| R15 | **Simulator drift** (Icarus 12 in Docker vs 13 local) | L | L | identical verdicts on 2 runs | pin one image for the benchmark; record `image_id` | P1 |
| R16 | **Vision wording ("world model", "Physical AI") reaches the pitch** | M | M | vision text vs `CLAUDE.md` §8 | ADR-002; grep check in acceptance criteria | P1 |

## 2. Inversion review of the key decisions

| Decision | What would make it fail | Early signal | Response |
| --- | --- | --- | --- |
| ADR-001 Tools decide | The oracle itself is wrong, and the tools faithfully confirm a wrong design | An external spec reader finds a behaviour the golden model gets wrong | Independent formal properties; second-author oracle |
| ADR-002 No world model | A downstream (timing/PPA) problem appears where simulation is the bottleneck | Synthesis/STA time per candidate ≫ model time once G4 exists | Revisit with logged synthesis data; measure before building |
| ADR-003 Single pipeline | Several blocks or oracles need concurrent, heterogeneous steps | More than one oracle per block, or a parallel candidate search | Add typed steps; still deterministic control |
| ADR-006 Two-rule gate | A real block needs system tasks or directives | Next block needs `$clog2` or parameters via `` `define `` | Reviewed per-token exceptions, not a blanket relaxation |
| ADR-007 G3 sweep | Sweep shares the golden model's blind spots | A defect found outside the team that both suites miss | Independent oracle authorship (V-4) |
| ADR-008 Trust-layer lead | Judges reward raw generation over evidence | Feedback from viewers of the video | The loop is still there; the claim is narrower, not absent |
| ADR-009 Static public surface | Judges expect to trigger a live run | Judging guidance or the reviewer explicitly asks for one | Token-gated live endpoint as a stretch goal if credits and time allow |
| ADR-011 Arm design | Arm B written by someone who read the RTL leaks the answer anyway | B's results track A closely, with equation-like phrasing | Have the prose spec written from an external datasheet, or by a teammate who hasn't seen the RTL |

## 3. Kill criteria

These are proposals; thresholds should be agreed with Adrian. **Technical:**

1. **K-T1.** On ≥5 blocks held out from the authors, with prose specs and independently written tests, green within 3 repairs is below `[THRESHOLD]` %, or no better than a template or search baseline.
2. **K-T2.** Writing the golden model and tests for a new block takes as much engineer time as writing the RTL by hand, and AI oracle drafting (V-4) doesn't change that.
3. **K-T3.** The shared-misreading rate between AI-drafted oracle and AI-drafted RTL from the same spec is high enough that independence can't be claimed.

**Commercial:**

4. **K-C1.** Fewer than 3 of about 10 interviewed DV/RTL/CAD engineers name verification evidence or testbench qualification as a cost they would pay to cut.
5. **K-C2.** Incumbent EDA AI agents already provide independent grading, mutation qualification and replayable evidence for generated RTL. Not checked: their primary pages don't state it (`01` §2D).
6. **K-C3.** No design partner will run their own block within 60 days of the hackathon.

## 4. Hackathon cut list (cut from the top when late)

Agreed with red-team pass 2. It extends the cut order in `CLAUDE.md` §6.

1. Hosted live simulation on Modal (Volume, cancel, 429, queue caps). Public surface stays static with replay (ADR-009, Adrian decides).
2. Baseten repair arm (credits unapproved; price unset).
3. Benchmark beyond arms A, B, C and the baseline.
4. Structured JSON repair output.
5. Provenance block and schema versions (keep `git_commit` + toolchain only).
6. Run Console screen (keep the Evidence Board).
7. Image/PDF extraction, unless it works by 2 Nov. If kept, label it interface-guarded AI interpretation.

**Never cut:**
- Replay fix.
- Two-rule gate + compile check.
- Docker-only live runs.
- Extended suite hash.
- Fail-closed token.
- Parameter sweep.
- Independently written prose spec.
- Every attempt counted.
- Real simulation, seeded failure, repair + full rerun.
- Evidence record.
- Mutation check.

## 5. Unresolved: requires people or experiments, not more architecture

| Question | Needs |
| --- | --- |
| Do DV/RTL teams want a trust gate, and would they pay? | 5–10 user interviews |
| What does onboarding a block from outside the team cost? | One design partner |
| Does Muse Spark pass a prose-only spec? | Arm B (about $0.30) |
| Do the live RTLs survive the parameter sweep? | One G3 run |
| Does a process spawned inside Docker race `results.xml`? | A probe with process spawn |
| Meta and Baseten retention and training terms (Standard mode) | Read provider terms / DPA |
| Which next block convinces an RTL team (AXI-Stream skid buffer, arbiter, async FIFO)? | RTL engineer interviews |
| Are Modal and Baseten credits approved? | Adrian |
| Is Yosys acceptable under the "one simulator" rule? | Adrian |
