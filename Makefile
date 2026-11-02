RTL ?= rtl/sync_fifo.v
RUN ?= manual
IMAGE = davinci-sim:latest

.PHONY: sim mutate weak-demo image sandbox api evidence board plan plan-ref gaps coverage coverage-ref trace trace-ref triage

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

# Scenario counters (full, empty, overflow case, wraparound, ...) from a waveform
# of the frozen suite: on a stored run's final RTL inside Docker, or on the reference RTL.
coverage:
	python3 verify/coverage.py --run runs/$(RUN)

coverage-ref:
	python3 verify/coverage.py --reference

# Test credibility for failure triage ("design or test?"): reference RTL verdict,
# planted bugs each test kills, situations it drives. Run after plan-ref, mutate,
# gaps and trace-ref.
triage:
	python3 verify/triage.py

# Per-cycle traces (waveform + FIFO views): every simulated attempt of a run, in Docker.
trace:
	python3 verify/trace.py --run runs/$(RUN)

trace-ref:
	python3 verify/trace.py --reference

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
# Until it is hosted, it runs here and the Vercel board connects to it from this
# machine's browser (Connection settings → http://127.0.0.1:8000). Model-written
# RTL still runs only in the local Docker sandbox, so Docker must be running.
CORS ?= https://davinci-silicon-fe.vercel.app,http://127.0.0.1:4320,http://localhost:3000
api:
	DAVINCI_CORS_ORIGINS="$(CORS)" uvicorn api.server:app --host 127.0.0.1 --port 8000

# Committed evidence bundle for the Evidence Board (live runs + today's-gates replays).
LIVE ?= live01 live02-m1 live03-pdf live04-breakdown
evidence:
	python3 scripts/export_evidence.py $(LIVE)

# Static Evidence Board from evidence/ -> web/out (set NEXT_PUBLIC_DAVINCI_API for live replay).
board:
	cd web && npm ci --no-audit --no-fund && npx next build
