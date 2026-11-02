"""Frozen cocotb test suite for sat_gain. Every cycle compares the DUT with the
bit-accurate golden model (golden_model.py, integers only). Each test names
the requirement it covers (see blocks/sat_gain/requirements.json).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from golden_model import SatGainModel

FIELDS = ["y", "sat"]


def code(v: int) -> int:
    """Signed value -> 8-bit two's complement code."""
    return v & 0xFF


class Harness:
    def __init__(self, dut, req):
        self.dut, self.req = dut, req
        self.model = SatGainModel()
        self.cycle_no = 0

    async def start(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, unit="ns").start())
        await self.cycle(rst=1)
        await self.cycle(rst=1)

    async def cycle(self, x=0, g=0, rst=0):
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.rst.value = rst
        dut.x.value = code(x)
        dut.g.value = code(g)
        await RisingEdge(dut.clk)
        exp = self.model.step(code(x), code(g), rst)
        await ReadOnly()
        self.cycle_no += 1
        for f in FIELDS:
            got = int(getattr(dut, f).value)
            assert got == exp[f], (
                f"{self.req} cycle {self.cycle_no}: {f} expected {exp[f]:#04x}, got {got:#04x} "
                f"(inputs x={code(x):#04x} g={code(g):#04x} rst={rst})"
            )
        return exp


@cocotb.test()
async def test_reset_state(dut):
    """REQ-01: synchronous reset clears y and sat."""
    h = Harness(dut, "REQ-01")
    await h.start()
    await h.cycle(x=-128, g=-128)  # saturating product: y = 0x7f, sat = 1
    exp = await h.cycle(x=-128, g=-128, rst=1)
    assert exp["y"] == 0 and exp["sat"] == 0


@cocotb.test()
async def test_latency(dut):
    """REQ-02: y shows the product of the inputs sampled at the previous edge."""
    h = Harness(dut, "REQ-02")
    await h.start()
    for x, g in [(64, 64), (0, 0), (96, 64), (-64, 64), (0, 0), (127, 0)]:
        await h.cycle(x=x, g=g)


@cocotb.test()
async def test_max_positive(dut):
    """REQ-03: max positive x max positive = 0x7e (126/128), no saturation."""
    h = Harness(dut, "REQ-03")
    await h.start()
    exp = await h.cycle(x=127, g=127)
    assert exp["y"] == 0x7E and exp["sat"] == 0


@cocotb.test()
async def test_neg_one_squared_saturates(dut):
    """REQ-04: -1 x -1 = +1 does not fit Q1.7: y clamps to 0x7f and sat pulses."""
    h = Harness(dut, "REQ-04")
    await h.start()
    exp = await h.cycle(x=-128, g=-128)
    assert exp["y"] == 0x7F and exp["sat"] == 1
    exp = await h.cycle(x=1, g=1)
    assert exp["sat"] == 0


@cocotb.test()
async def test_truncation_negative(dut):
    """REQ-05: negative products truncate toward minus infinity (never toward zero, never rounded)."""
    h = Harness(dut, "REQ-05")
    await h.start()
    for x, g in [(-1, 1), (-3, 5), (-127, 1), (1, -127), (-64, 3), (-5, 77), (-100, 100)]:
        await h.cycle(x=x, g=g)
    exp = await h.cycle(x=-1, g=1)
    assert exp["y"] == 0xFF  # -1/16384 truncates to -1/128, not 0


@cocotb.test()
async def test_truncation_positive(dut):
    """REQ-05: positive products drop the fraction (no round-to-nearest)."""
    h = Harness(dut, "REQ-05")
    await h.start()
    for x, g in [(1, 127), (3, 43), (11, 12), (100, 100), (127, 65)]:
        await h.cycle(x=x, g=g)
    exp = await h.cycle(x=1, g=127)
    assert exp["y"] == 0  # 127/16384 is just under 1/128: truncates to 0


@cocotb.test()
async def test_sign_combinations(dut):
    """REQ-06: operands are two's complement signed; all four sign quadrants."""
    h = Harness(dut, "REQ-06")
    await h.start()
    for x in (-128, -77, -1, 0, 1, 77, 127):
        for g in (-128, -77, -1, 0, 1, 77, 127):
            await h.cycle(x=x, g=g)


@cocotb.test()
async def test_random_regression(dut):
    """REQ-01..06: 3000 random cycles with occasional reset, fixed seed."""
    h = Harness(dut, "REQ-01..06")
    rng = random.Random(0x5A7)
    await h.start()
    for _ in range(3000):
        await h.cycle(x=rng.randint(-128, 127), g=rng.randint(-128, 127), rst=int(rng.random() < 0.02))
