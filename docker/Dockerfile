# DaVINCI simulation sandbox: Icarus Verilog + cocotb, runs untrusted RTL.

# cocotb has no prebuilt wheel for every platform (e.g. linux/arm64), so build
# it here; the final image carries no compiler.
FROM python:3.12-slim AS wheels
RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ \
 && rm -rf /var/lib/apt/lists/*
RUN pip wheel --no-cache-dir --wheel-dir /wheels cocotb==2.1.0

FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends iverilog \
 && rm -rf /var/lib/apt/lists/*
COPY --from=wheels /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links /wheels cocotb==2.1.0 && rm -rf /wheels

RUN useradd --create-home --uid 1000 sim
WORKDIR /work
COPY tests/  /work/tests/
COPY verify/ /work/verify/
COPY tests_sweep/ /work/tests_sweep/
COPY spec/interface.json /work/spec/interface.json
RUN chmod -R a-w /work/tests /work/verify /work/tests_sweep /work/spec
USER sim

# The RTL under test is mounted at /work/in/dut.v, results go to /work/out.
# The parameter sweep and scenario counters run with --entrypoint timeout ...
# python verify/run_sweep.py / verify/coverage.py.
ENTRYPOINT ["timeout", "120", "python", "verify/run_suite.py", "/work/in/dut.v", "--out", "/work/out"]
