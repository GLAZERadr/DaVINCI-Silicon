"""Candidate tests for sat_gain whose expected values come from the naive float
model (float_model.py), not from the bit-accurate golden model. Not frozen and
not pinned: they have not yet been shown to agree with the reference RTL.
verify/triage_block.py runs them on the reference RTL and reports the result.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from float_model import FloatGainModel


class Harness:
    def __init__(self, dut, label):
        self.dut, self.label = dut, label
        self.model = FloatGainModel()
        self.cycle_no = 0

    async def start(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, unit="ns").start())
        await self.cycle(rst=1)

    async def cycle(self, x=0, g=0, rst=0):
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.rst.value = rst
        dut.x.value = x & 0xFF
        dut.g.value = g & 0xFF
        await RisingEdge(dut.clk)
        exp = self.model.step(x, g, rst)
        await ReadOnly()
        self.cycle_no += 1
        got = int(dut.y.value)
        assert got == exp["y"], (
            f"{self.label} cycle {self.cycle_no}: y expected {exp['y']:#04x} (float model), got {got:#04x} "
            f"(inputs x={x & 0xFF:#04x} g={g & 0xFF:#04x} rst={rst})")


@cocotb.test()
async def test_corner_cases_float(dut):
    """Spec corner cases, expected values from the float model."""
    h = Harness(dut, "float-model corners")
    await h.start()
    for x, g in [(127, 127), (-128, -128), (-1, 1), (1, 127)]:
        await h.cycle(x=x, g=g)


@cocotb.test()
async def test_random_regression_float(dut):
    """1000 random cycles, expected values from the float model."""
    h = Harness(dut, "float-model random")
    rng = random.Random(0x5A7)
    await h.start()
    for _ in range(1000):
        await h.cycle(x=rng.randint(-128, 127), g=rng.randint(-128, 127))
