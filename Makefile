RTL ?= rtl/sync_fifo.v
RUN ?= manual
IMAGE = davinci-sim:latest

.PHONY: sim mutate weak-demo image sandbox api

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

# HTTP API for the UI (runs execute one at a time in a background worker).
api:
	uvicorn api.server:app --port 8000
