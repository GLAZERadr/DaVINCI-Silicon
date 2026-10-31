# 05 — Architecture decision records

Format: context → decision → alternatives → rationale and evidence → trade-offs → reversibility. "Proposed" means recommended by this review and awaiting Adrian. "Accepted" means already in the code or in `CLAUDE.md`.

---

## ADR-001 · Deterministic tools decide; models only propose
**Status:** Accepted (in code), reaffirmed.
**Context:** The core risk is false confidence in model output.
**Decision:**
- Verdicts come only from a simulator or compiler.
- Model text is stored and labelled "AI interpretation · not verified".
- Models never touch `tests/`, never decide stop conditions, never grade.

**Alternatives:** LLM-as-judge; model-decided stopping; tool-calling loops where the model triggers simulation.
**Rationale:** 8/8 reviewers. The frozen, hashed suite is the only part of the system an RTL team would trust (`agent/pipeline.py`, `verify/suite.sha256`).
**Trade-offs:** blocks without a hand-written oracle can't be verified. That is the main scaling cost (ADR-007).
**Reversibility:** easy to loosen, very costly to regain trust once loosened. Treat as permanent.

## ADR-002 · No learned world model; the cycle-accurate reference model plus simulator fills that role
**Status:** Proposed.
**Context:** The vision says "Physical AI and World Models". The code has none, and `CLAUDE.md` §8 bans the terms in copy.
**Decision:** Remove world model and digital twin from the architecture. Describe `tests/golden_model.py` as a cycle-accurate reference model. Keep a PPA surrogate as deferred research with no build trigger set.
**Alternatives:** learned dynamics model of the DUT; surrogate test-outcome predictor; general physical world model.
**Rationale:**
- An exact transition function already exists.
- Simulation (0.23–0.39 s) costs 1–6 % of a model call (6–27 s), so prediction saves nothing (`runs/live*/run.json`).
- No synthesis data exists for any PPA model.

**Trade-offs:** the company vision and the hackathon product diverge in wording. The pitch must not claim what isn't built.
**Reversibility:** fully reversible. Nothing is built; revisit when downstream data exists.

## ADR-003 · Single deterministic pipeline; no runtime multi-agent framework
**Status:** Accepted (`CLAUDE.md` §2), reaffirmed.
**Decision:** one loop in `agent/pipeline.py` with typed model calls. Add the stop states `truncated`, `no_progress` and `needs_engineer`.
**Alternatives:** planner/coder/verifier agent team; agent framework.
**Rationale:** no task here needs parallel or debating agents (AI reviewer). Fewer moving parts gives cleaner evidence. Incumbents' multi-agent products are not evidence of necessity.
**Trade-offs:** adding blocks or oracles later means adding typed steps, not agents.
**Reversibility:** easy. Steps can be wrapped as agents later without changing the evidence model.

## ADR-004 · Self-contained run directories; replay reads the run's own responses
**Status:** Proposed (fixes a verified defect, V1).
**Context:** A shared cache keyed by prompt hash was overwritten by fake runs, breaking replay of both live runs.
**Decision:**
- Replay reads `runs/<source>/attempt_n/response.md` in `calls.jsonl` order.
- `calls.jsonl` records `response_sha256`.
- Any cache is keyed by provider, model and request, and never overwrites. The fake provider never writes shared state.

**Alternatives:** per-run cache dir (red team); content-addressed blobs (verification).
**Rationale:** all three fix V1. This one adds no new storage and makes each run directory portable into the evidence bundle.
**Trade-offs:** slight duplication of response text. Negligible.
**Reversibility:** easy.

## ADR-005 · Files plus JSONL now; Postgres and object store later; knowledge graph deferred
**Status:** Proposed.
**Decision:** keep `runs/` and JSONL for the hackathon, and commit a hashed `evidence/` bundle for the submission. Move to Postgres (runs, attempts, calls, approvals) plus content-addressed object storage at multi-user scale. Add a graph only if cross-block queries appear.
**Alternatives:** knowledge graph now; database now.
**Rationale:** no query exists that a graph answers better than a join (data reviewer). One user, one machine.
**Trade-offs:** no concurrent writers; the evidence lives in git.
**Reversibility:** easy. Records are already structured JSON.

## ADR-006 · Static gate is a two-rule ban plus a compile check, not an allowlist parser
**Status:** Proposed (fixes V2).
**Decision:**
- Reject any `$` and any backtick except `` `timescale ``.
- Require `iverilog -g2001 -Wall` compile-only success and a matching port list.
- Run model RTL only in the Docker sandbox.

**Alternatives:** keep the denylist (bypassed, V2); a full Verilog allowlist parser (platform reviewer).
**Rationale:** the FIFO needs neither system tasks nor directives. The reference and both live RTLs contain none (checked). Two rules close the confirmed `` `define ``/`` `` `` bypass. The sandbox, not the regex, is the boundary (red team pass 2).
**Trade-offs:** future blocks needing `$clog2` need an explicit, reviewed exception.
**Reversibility:** easy.

## ADR-007 · Verification gates G0–G3 now; G4 (synthesis, formal) after the hackathon
**Status:** Proposed.
**Decision:**
- G0 suite readiness.
- G1 static.
- G2 frozen suite.
- G3 parameter sweep as a separate versioned suite, never shown to the model.
- A G2 pass with a G3 fail is `escaped`, not `pass`.
- Yosys synthesis only if Adrian accepts the scope change; otherwise post-hackathon with SymbiYosys equivalence.

**Alternatives:** modify the frozen suite to add parameters (violates the freeze rule); extra random seeds as holdout (red team: near-zero added value, since the existing regression already kills all mutants).
**Rationale:**
- A pass today is valid at one parameter point only (4 reviewers).
- Separate files keep the frozen suite untouched.
- The sweep catches the one realistic escape: hard-coded widths.

**Trade-offs:** G3 shares the golden model and author with G2, so a shared misreading of the spec stays invisible (red team).
**Reversibility:** easy.

## ADR-008 · Lead with the trust layer; generation is one input; product pivot is a hypothesis
**Status:** Proposed. **Adrian decides** (affects pitch and video).
**Context:** "Generate, simulate, repair" is shipped or piloted by Synopsys, Siemens, Cadence and ChipAgents (workflow reviewer, URLs in `01`). Verification dominates engineering time (Wilson 2022).
**Decision:**
- *Hackathon:* keep Muse Spark generation (judging requires real Meta model use), but open the demo with the weak-test catch and replay. Narrow the claim to "spec-conformant generation under independent verification, one block".
- *Post-hackathon:* test the hypothesis "trust gate for RTL from any source" with interviews and one block from outside the team before building for it.

**Alternatives:**
- (a) Generation as the product.
- (b) The AI drafts oracles instead of RTL (red team alternative). Kept as a post-hackathon experiment that requires independent authorship of oracle and RTL.

**Rationale:** differentiation evidence plus cost-of-verification evidence. Not settled: zero user interviews.
**Trade-offs:** a less flashy pitch. Risk that the trust gate relocates rather than removes the oracle-authoring cost (red team pass 2).
**Reversibility:** pitch is easy to change; product direction is costly once built, hence "hypothesis" until V-1/V-2 in `04`.

## ADR-009 · Public hackathon surface is a static Evidence Board over a committed bundle
**Status:** Proposed. **Conflicts with `CLAUDE.md` §6 Deploy task (hosted API + Modal simulations). Adrian decides.**
**Decision:** serve a static board with replay over `evidence/`. Build hosted live simulation (Modal Sandbox, Volume, queue caps, cancel) only if Modal credits are confirmed by 1 Nov and P0/P1 are done.
**Alternatives:** hosted live runs open to judges.
**Rationale:**
- A public live endpoint adds budget-abuse, sandbox-escape and availability risk.
- Its components (verdict on stdout, Volume, rate limits, cancel) are unbuilt and untested.
- Credit approval is unknown (`CLAUDE.md` §9).
- A recorded run was already required as the fallback.

**Trade-offs:** judges can't trigger a fresh model call themselves. The video and code must carry "real Meta model use".
**Reversibility:** easy. The API exists; hosting can be added later.

## ADR-010 · Fail-closed security defaults
**Status:** Proposed (P0).
**Decision:**
- Live-provider runs require a token, checked with `compare_digest`.
- No client-selectable sandbox; no local simulation of model RTL.
- The local subprocess gets a scrubbed env.
- The pinned hash covers `verify/run_suite.py` and `verify/mutants.json`.

**Rationale:** the current defaults are open (`api/server.py:62,131-134`, `agent/pipeline.py:117-119`). Combined with V2 this is a verified file-write path on the host.
**Reversibility:** easy.

## ADR-011 · Benchmark arms by condition, not one prompt sampled N times
**Status:** Proposed.
**Decision:** arms A (equation spec), B (independently written prose spec), C (M1–M8 seeded once each) plus an inverse-mutant baseline. N = 10 for A and B, with Wilson intervals. One simulator image; no cache reads.
**Alternatives:** N ≥ 10 of the same prompt (`CLAUDE.md` §6); N ≥ 30 per cell over a 36-cell matrix (AI reviewer).
**Rationale:** the same prompt sampled 10 times measures sampling noise on a spec that contains the answer. The full matrix is about 360 runs of analysis before the UI exists (red team pass 2). Cost is about $1, so the limit is time.
**Trade-offs:** fewer conditions (no Baseten arm unless credits arrive).
**Reversibility:** easy. More arms can be added later.
