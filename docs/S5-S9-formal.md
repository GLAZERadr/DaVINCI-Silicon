# S5 / S9 — Formal checks with SymbiYosys

Stretch items S5 (bounded) and S9 (unbounded) from `docs/UPDATE-2026-11-02.md`.

## What runs

- **Properties**: `formal/sync_fifo_props.sv`, hand-written, pinned in `formal/props.sha256`, never in a
  model prompt. A wrapper module `fifo_formal` instantiates `sync_fifo` with the default parameters
  (WIDTH 8, DEPTH 16, AF_THRESH 14) and uses only the ports, so it checks any RTL with the right interface.
  Only assumption: reset in the first cycle; all other inputs are free.

  | ID | Property |
  | --- | --- |
  | P1 | `count <= DEPTH` |
  | P2 | `full == (count == DEPTH)` |
  | P3 | `empty == (count == 0)` |
  | P4 | never `full && empty` |
  | P5 | `overflow` only after a write while full, with no read and no reset, on the previous cycle |
  | P6 | `count` changes by at most 1 per cycle outside reset (a wrap 0 → 31 counts as a jump) |

- **Per property** (each enabled on its own, so each has its own result):
  1. BMC, depth 20 (`smtbmc z3`) → "holds for 20 cycles" or "failed" (counterexample VCD stored).
  2. Prove mode: k-induction (`smtbmc z3`, depth 20); if induction does not close, `abc pdr`.
     Reported as **proved (unbounded)** only when an engine returns PASS; otherwise
     **bounded only (depth 20)**; base-case failure → **failed**.
- **Sandbox**: image `davinci-sim:formal` (`docker/Dockerfile.formal`, `make formal-image`): Debian trixie,
  Yosys 0.52, yosys-abc, Z3 4.13.3, SymbiYosys v0.52 (commit 1b36b27). Same `DOCKER_LIMITS` as the
  simulation sandbox (no network, 1 CPU, 512 MB, 256 pids, read-only root, no capabilities), uid 1000,
  `timeout 600` inside. The host aborts when the container's `verify/formal.py` or property hash differs
  from the repo (stale image). `davinci-sim:latest` is not touched.
- **Commands**: `make formal RUN=<id>` (run's final simulated RTL → `runs/<id>/formal/`),
  `make formal-ref` (→ `runs/reference/formal/`), `make formal-mutants`
  (→ `runs/reference/formal/mutants/<M>/formal/`, summary merged into the reference `formal.json`).
  Each output dir has `formal.json`, `logs/<prop>_{bmc,kind,pdr}.log`, `cex/*.vcd` on failure.

## Measured results (2 Nov 2026, local Docker, $0)

Reference RTL: 6/6 hold for 20 cycles; 6/6 proved (unbounded). P1–P5 by k-induction; P6 induction did
not close at depth 20 (UNKNOWN), `abc pdr` proved it. Total 13 s.

Mutants (`verify/mutants.json`): formal catches **3/8**.

| Mutant | Result | Failing property (cex step) |
| --- | --- | --- |
| M2 full one entry early | caught | P2 (step 16) |
| M7 read when empty is a real read | caught | P1, P6 (step 2) |
| M8 overflow despite same-cycle read | caught | P5 (step 18) |
| M1, M3, M4, M5, M6 | not caught | — these break write-when-full-with-read, almost_full, read-pointer wrap, underflow, dout reset: no property states them. The simulation suite kills all 8. |

Model RTL (final attempt of each stored live run, checked in Docker): live01 (attempt 1), live02-m1
(attempt 2), live03-pdf (attempt 1), live04-breakdown (attempt 2) — each 6/6 hold for 20 cycles and
6/6 proved (unbounded); one property per design needed `abc pdr` (P6, or P5 for live03-pdf).

## Scope

- Control/flag properties are proved. Data ordering (FIFO order, `dout` values) is covered by simulation
  against the golden model, not by formal.
- No helper invariants were needed: where k-induction did not close, `abc pdr` did. If a future design
  leaves a property at "bounded only", that is what is reported.
- Not wired into `agent/pipeline.py` or the API worker: formal runs as a separate step on stored runs.
- Evidence bundle: `scripts/export_evidence.py` copies `formal.json` (run + reference); logs and
  counterexample VCDs stay in `runs/`.
