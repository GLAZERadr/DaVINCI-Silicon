"""Parameter sweep for sync_fifo: the same golden model and the same
every-cycle comparison as the frozen suite, at parameter sets other than the
defaults. Results are never shown to the model. Pinned in verify/sweep.sha256.

Parameters come from SWEEP_WIDTH / SWEEP_DEPTH / SWEEP_AF (set by
verify/run_sweep.py, which also builds the DUT with matching parameters).
"""
import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))  # the frozen golden model
from golden_model import FifoModel  # noqa: E402

WIDTH, DEPTH, AF = (int(os.environ[k]) for k in ("SWEEP_WIDTH", "SWEEP_DEPTH", "SWEEP_AF"))
FIELDS = ["dout", "count", "full", "empty", "almost_full", "overflow", "underflow"]
TAG = f"WIDTH={WIDTH} DEPTH={DEPTH} AF_THRESH={AF}"


class Harness:
    def __init__(self, dut):
        self.dut = dut
        self.model = FifoModel(WIDTH, DEPTH, AF)
        self.cycle_no = 0

    async def start(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, unit="ns").start())
        await self.cycle(rst=1)
        await self.cycle(rst=1)

    async def cycle(self, wr=0, din=0, rd=0, rst=0):
        dut = self.dut
        din &= (1 << WIDTH) - 1
        await FallingEdge(dut.clk)
        dut.rst.value, dut.wr_en.value, dut.din.value, dut.rd_en.value = rst, wr, din, rd
        await RisingEdge(dut.clk)
        exp = self.model.step(wr, din, rd, rst)
        await ReadOnly()
        self.cycle_no += 1
        for f in FIELDS:
            got = int(getattr(dut, f).value)
            assert got == exp[f], (f"[{TAG}] cycle {self.cycle_no}: {f} expected {exp[f]:#x}, got {got:#x} "
                                   f"(wr_en={wr} din={din:#x} rd_en={rd} rst={rst})")


@cocotb.test()
async def test_sweep_directed(dut):
    """Fill, overflow, full read+write, drain, underflow, empty read+write."""
    h = Harness(dut)
    await h.start()
    for i in range(DEPTH):
        await h.cycle(wr=1, din=0x5A + i)
    await h.cycle(wr=1, din=0xFF)              # write when full, no read
    for i in range(3):
        await h.cycle(wr=1, din=0xA0 + i, rd=1)  # read + write when full
    for _ in range(DEPTH):
        await h.cycle(rd=1)
    await h.cycle(rd=1)                         # read when empty
    await h.cycle(wr=1, din=0x33, rd=1)         # read + write when empty
    await h.cycle(rd=1)


@cocotb.test()
async def test_sweep_random(dut):
    """Seeded random traffic with wraparound, checked every cycle."""
    h = Harness(dut)
    await h.start()
    rng = random.Random(1000 * DEPTH + WIDTH)
    for _ in range(1500):
        bias = rng.random()
        await h.cycle(wr=int(rng.random() < bias), din=rng.randrange(1 << WIDTH),
                      rd=int(rng.random() < 1 - bias), rst=int(rng.random() < 0.003))
