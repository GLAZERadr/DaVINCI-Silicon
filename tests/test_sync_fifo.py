"""Frozen cocotb test suite for sync_fifo. Every check compares the DUT with
the golden model on every cycle. Each test names the requirement it covers
(see spec/requirements.json).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from golden_model import FifoModel

DEPTH, WIDTH, AF = 16, 8, 14
FIELDS = ["dout", "count", "full", "empty", "almost_full", "overflow", "underflow"]


class Harness:
    def __init__(self, dut, req):
        self.dut, self.req = dut, req
        self.model = FifoModel(WIDTH, DEPTH, AF)
        self.cycle_no = 0

    async def start(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, unit="ns").start())
        await self.cycle(rst=1)
        await self.cycle(rst=1)

    async def cycle(self, wr=0, din=0, rd=0, rst=0):
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.rst.value = rst
        dut.wr_en.value = wr
        dut.din.value = din
        dut.rd_en.value = rd
        await RisingEdge(dut.clk)
        exp = self.model.step(wr, din, rd, rst)
        await ReadOnly()
        self.cycle_no += 1
        for f in FIELDS:
            got = int(getattr(dut, f).value)
            assert got == exp[f], (
                f"{self.req} cycle {self.cycle_no}: {f} expected {exp[f]:#x}, got {got:#x} "
                f"(inputs wr_en={wr} din={din:#x} rd_en={rd} rst={rst})"
            )
        return exp


@cocotb.test()
async def test_reset_state(dut):
    """REQ-01: after reset the FIFO is empty, count 0, dout 0, no flags."""
    h = Harness(dut, "REQ-01")
    await h.start()
    for _ in range(3):
        await h.cycle(wr=1, din=0xAA)
    exp = await h.cycle(rst=1)
    assert exp["empty"] == 1 and exp["count"] == 0


@cocotb.test()
async def test_full_flag(dut):
    """REQ-03, REQ-09: full asserts exactly when DEPTH entries are stored."""
    h = Harness(dut, "REQ-03")
    await h.start()
    for i in range(DEPTH):
        exp = await h.cycle(wr=1, din=i)
        assert exp["full"] == (1 if i == DEPTH - 1 else 0)


@cocotb.test()
async def test_empty_flag(dut):
    """REQ-03: empty asserts exactly when the last entry is read."""
    h = Harness(dut, "REQ-03")
    await h.start()
    for i in range(4):
        await h.cycle(wr=1, din=0x10 + i)
    for i in range(4):
        exp = await h.cycle(rd=1)
        assert exp["empty"] == (1 if i == 3 else 0)


@cocotb.test()
async def test_wraparound_order(dut):
    """REQ-02: data leaves in write order across pointer wraparound."""
    h = Harness(dut, "REQ-02")
    await h.start()
    val = 0
    for burst in (10, 16, 7, 16):
        for _ in range(burst):
            await h.cycle(wr=1, din=val & 0xFF)
            val += 1
        for _ in range(burst):
            await h.cycle(rd=1)


@cocotb.test()
async def test_overflow(dut):
    """REQ-04: a write when full (no read) is ignored and flags overflow."""
    h = Harness(dut, "REQ-04")
    await h.start()
    for i in range(DEPTH):
        await h.cycle(wr=1, din=i)
    exp = await h.cycle(wr=1, din=0xEE)
    assert exp["overflow"] == 1 and exp["count"] == DEPTH
    for _ in range(DEPTH):
        await h.cycle(rd=1)


@cocotb.test()
async def test_underflow(dut):
    """REQ-05: a read when empty is ignored, flags underflow, dout holds."""
    h = Harness(dut, "REQ-05")
    await h.start()
    await h.cycle(wr=1, din=0x5A)
    await h.cycle(rd=1)
    exp = await h.cycle(rd=1)
    assert exp["underflow"] == 1 and exp["dout"] == 0x5A


@cocotb.test()
async def test_full_simultaneous_rw(dut):
    """REQ-06: read + write when full reads the oldest, stores the new word."""
    h = Harness(dut, "REQ-06")
    await h.start()
    for i in range(DEPTH):
        await h.cycle(wr=1, din=0x30 + i)
    for i in range(4):
        exp = await h.cycle(wr=1, din=0xA0 + i, rd=1)
        assert exp["count"] == DEPTH
    for _ in range(DEPTH):
        await h.cycle(rd=1)


@cocotb.test()
async def test_empty_simultaneous_rw(dut):
    """REQ-07: read + write when empty stores the word and flags underflow."""
    h = Harness(dut, "REQ-07")
    await h.start()
    exp = await h.cycle(wr=1, din=0x77, rd=1)
    assert exp["count"] == 1 and exp["underflow"] == 1
    await h.cycle(rd=1)


@cocotb.test()
async def test_almost_full(dut):
    """REQ-08: almost_full is high exactly when count >= AF_THRESH."""
    h = Harness(dut, "REQ-08")
    await h.start()
    for i in range(DEPTH):
        exp = await h.cycle(wr=1, din=i)
        assert exp["almost_full"] == int(i + 1 >= AF)
    for _ in range(DEPTH):
        await h.cycle(rd=1)


@cocotb.test()
async def test_random_regression(dut):
    """REQ-01..09: 3000 random cycles checked against the golden model."""
    h = Harness(dut, "REQ-ALL")
    await h.start()
    rng = random.Random(20261105)
    for _ in range(3000):
        bias = rng.random()
        await h.cycle(
            wr=int(rng.random() < bias),
            din=rng.randrange(256),
            rd=int(rng.random() < 1 - bias),
            rst=int(rng.random() < 0.002),
        )
