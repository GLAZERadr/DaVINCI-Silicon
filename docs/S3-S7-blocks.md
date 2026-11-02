# S3 + S7: block registry, sat_gain, rr_arbiter

## Registry (S7)

`blocks/<name>/block.json` describes one block: spec, requirements, interface,
reference RTL, frozen tests + golden model, mutants, top module, runner and
suite pin. Three blocks are registered:

| Block | Files | Runner | Suite pin | G3 sweep |
| --- | --- | --- | --- | --- |
| `sync_fifo` | unchanged paths (`spec/`, `rtl/`, `tests/`, `verify/mutants.json`) | `verify/run_suite.py` (frozen) | `verify/suite.sha256` | yes |
| `sat_gain` | `blocks/sat_gain/` | `verify/run_block.py` | `blocks/sat_gain/suite.sha256` | no (FIFO only) |
| `rr_arbiter` | `blocks/rr_arbiter/` | `verify/run_block.py` | `blocks/rr_arbiter/suite.sha256` | no (FIFO only) |

The FIFO did not move: its paths are inside its pinned suite hash. Other
blocks' suite hash covers the files their block.json lists under `frozen`
(tests, golden model, `verify/run_block.py`, mutants); editing any of them
changes the hash and the pipeline aborts until the pin is regenerated.

`python -m agent.pipeline --block <name>` (default `sync_fifo`). For
`sync_fifo` the prompts, gates, suite hash and run.json are unchanged (fake
dry runs with and without `--seed-bug M1` compared file by file before and
after, timings excluded). Other blocks: same G1 gates (no `$`, no directives,
no `initial`/`#`, port check against the block's interface, `iverilog
-g2001 -Wall`), no G3 sweep (`run.json` says so), `block` recorded in
run.json. `--breakdown`, spec intake and custom specs stay FIFO-only.
API: `GET /blocks`; `POST /runs` takes `block`. New run page shows a block
selector only when `/blocks` lists more than one block.

## sat_gain (S3)

Q1.7 x Q1.7, truncated (arithmetic shift, toward minus infinity), saturated
to Q1.7, registered, synchronous reset. Bit-accurate golden model in integers
(`blocks/sat_gain/tests/golden_model.py`), compared every cycle.

Float vs bit-accurate model (`make model-demo`): 1000 vectors (the spec's 4
corner cases, then random with seed 2026) driven into the reference RTL in
Icarus; the RTL outputs are measured, the counts are computed from them.
Written to `runs/blocks/sat_gain/model_demo/model_demo.json`.

Triage (`make block-triage BLOCK=sat_gain`): the candidate tests in
`blocks/sat_gain/candidate/` use the float model as their reference. They run
on the reference RTL and fail, so `runs/blocks/sat_gain/triage.json` labels
them "Test not yet validated · disagrees with the reference RTL"; the frozen
tests are "Test validated" (pass on the reference RTL, kill at least one
mutant). The FIFO triage (`verify/triage.py`) is unchanged.

## Commands

```bash
make block-evidence BLOCK=sat_gain     # reference verdict, mutation check, candidate tests, triage
make block-evidence BLOCK=rr_arbiter
make model-demo                        # S3 float vs bit-accurate, measured
python -m agent.pipeline --run-id sg1 --provider fake --block sat_gain --seed-bug M1
```

Not done: Evidence Board, verification plan, traces, coverage and gaps for
the new blocks (the FIFO only); the header breadcrumb still reads `sync_fifo`.
