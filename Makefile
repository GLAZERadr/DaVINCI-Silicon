RTL ?= rtl/sync_fifo.v
RUN ?= manual
IMAGE = davinci-sim:latest

.PHONY: sim mutate image sandbox

# Local run (needs iverilog + cocotb installed)
sim:
	python3 verify/run_suite.py $(RTL) --out runs/$(RUN)

mutate:
	python3 verify/mutate.py $(RTL) --out runs/mutation

image:
	docker build -f docker/Dockerfile -t $(IMAGE) .

# Sandboxed run: no network, capped CPU/memory/processes, read-only root,
# 120 s timeout inside the container, non-root user.
sandbox:
	mkdir -p runs/$(RUN)/in runs/$(RUN)/out
	cp $(RTL) runs/$(RUN)/in/dut.v
	docker run --rm --network none --cpus 1 --memory 512m --pids-limit 256 \
	  --read-only --tmpfs /tmp:size=64m \
	  -v $(PWD)/runs/$(RUN)/in:/work/in:ro \
	  -v $(PWD)/runs/$(RUN)/out:/work/out \
	  $(IMAGE)
