# DaVINCI simulation sandbox: Icarus Verilog + cocotb, runs untrusted RTL.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends iverilog make \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir cocotb==2.1.0

RUN useradd --create-home --uid 1000 sim
WORKDIR /work
COPY tests/  /work/tests/
COPY verify/ /work/verify/
RUN chmod -R a-w /work/tests /work/verify
USER sim

# The RTL under test is mounted at /work/in/dut.v, results go to /work/out.
ENTRYPOINT ["timeout", "120", "python", "verify/run_suite.py", "/work/in/dut.v", "--out", "/work/out"]
