"""cocotb module for the S3 model demo: drive a list of (x, g) vectors into the
RTL and record what it outputs. No expected values, no assertions: the
comparison with the two Python models happens afterwards, in
verify/model_demo.py. Vectors come from $DAVINCI_VECTORS, outputs go to
$DAVINCI_CAPTURE (both JSON files).
"""
import json
import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge


@cocotb.test()
async def capture(dut):
    vectors = json.loads(open(os.environ["DAVINCI_VECTORS"]).read())
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    out = []
    for i, (x, g) in enumerate([(0, 0)] + [tuple(v) for v in vectors]):
        await FallingEdge(dut.clk)
        dut.rst.value = 1 if i == 0 else 0
        dut.x.value = x & 0xFF
        dut.g.value = g & 0xFF
        await RisingEdge(dut.clk)
        await ReadOnly()
        if i:
            out.append({"x": x, "g": g, "y": int(dut.y.value), "sat": int(dut.sat.value)})
    with open(os.environ["DAVINCI_CAPTURE"], "w") as f:
        json.dump(out, f)
