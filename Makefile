RTL ?= rtl/sync_fifo.v
RUN ?= manual
IMAGE = davinci-sim:latest

.PHONY: sim mutate weak-demo image sandbox api evidence board plan plan-ref gaps

# Local run (needs iverilog + cocotb installed)
sim:
	python3 verify/run_suite.py $(RTL) --out runs/$(RUN)

mutate:
	python3 verify/mutate.py $(RTL) --out runs/mutation

image:
	docker build -f docker/Dockerfile -t $(IMAGE) .

# Sandboxed run: no network, capped CPU/memory/processes, read-only root,
# no capabilities, 120 s timeout inside the container, non-root user.
sandbox:
	mkdir -p runs/$(RUN)/in runs/$(RUN)/out
	cp $(RTL) runs/$(RUN)/in/dut.v
	docker run --rm --network none --cpus 1 --memory 512m --pids-limit 256 \
	  --read-only --tmpfs /tmp:size=64m --cap-drop ALL --security-opt no-new-privileges \
	  -v "$(CURDIR)/runs/$(RUN)/in:/work/in:ro" \
	  -v "$(CURDIR)/runs/$(RUN)/out:/work/out" \
	  $(IMAGE)

# Weak-test demo: leave out the REQ-06 tests, watch a mutant survive, then
# restore the full suite and watch it die.
weak-demo:
	python3 verify/mutate.py $(RTL) --weak-demo --out runs/weak_demo

# Coverage gaps: mutation check with each test left out (and each directed test
# together with the random regression); single-test kills; untargeted requirements.
gaps:
	python3 verify/gaps.py $(RTL) --out runs/coverage_gap

# Verification plan for a stored run: runs/$(RUN)/verification_plan.{md,json}.
# Reads stored files only (no simulation, no model call); output is reproducible.
plan:
	python3 verify/plan.py runs/$(RUN)

# Verification plan for the reference RTL (simulates it locally first).
plan-ref:
	python3 verify/run_suite.py $(RTL) --out runs/reference
	python3 verify/run_sweep.py $(RTL) --out runs/reference/sweep
	python3 verify/plan.py --reference runs/reference

# HTTP API for the UI (runs execute one at a time in a background worker).
api:
	uvicorn api.server:app --port 8000

# Committed evidence bundle for the Evidence Board (live runs + today's-gates replays).
LIVE ?= live01 live02-m1 live03-pdf
evidence:
	python3 scripts/export_evidence.py $(LIVE)

# Static Evidence Board from evidence/ -> web/out (set NEXT_PUBLIC_DAVINCI_API for live replay).
board:
	cd web && npm ci --no-audit --no-fund && npx next build
