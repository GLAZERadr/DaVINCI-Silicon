"""Frozen cocotb test suite for rr_arbiter. Every cycle compares the DUT with
the golden model, and checks three invariants directly: grant is one-hot or
zero, no grant without a request, and every request held high is granted
within 4 cycles. Each test names the requirement it covers
(see blocks/rr_arbiter/requirements.json).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from golden_model import N, ArbiterModel

MAX_WAIT = 4


class Harness:
    def __init__(self, dut, req):
        self.dut, self.req = dut, req
        self.model = ArbiterModel()
        self.cycle_no = 0
        self.wait = [0] * N  # consecutive edges requester i asked and was not granted

    async def start(self):
        cocotb.start_soon(Clock(self.dut.clk, 10, unit="ns").start())
        await self.cycle(rst=1)
        await self.cycle(rst=1)

    async def cycle(self, req=0, rst=0):
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.rst.value = rst
        dut.req.value = req
        await RisingEdge(dut.clk)
        exp = self.model.step(req, rst)
        await ReadOnly()
        self.cycle_no += 1
        where = f"{self.req} cycle {self.cycle_no}"
        got = int(dut.grant.value)
        assert got == exp["grant"], (
            f"{where}: grant expected {exp['grant']:#06b}, got {got:#06b} (inputs req={req:#06b} rst={rst})")
        assert got & (got - 1) == 0, f"{where}: grant {got:#06b} is not one-hot (REQ-03)"
        assert rst or got & ~req == 0, f"{where}: grant {got:#06b} without request (req={req:#06b}) (REQ-04)"
        for i in range(N):
            self.wait[i] = self.wait[i] + 1 if (req >> i & 1) and not (got >> i & 1) and not rst else 0
            assert self.wait[i] < MAX_WAIT, f"{where}: requester {i} waited {self.wait[i]} cycles (REQ-06)"
        return exp


@cocotb.test()
async def test_reset_state(dut):
    """REQ-01: reset clears grant and gives requester 0 the highest priority."""
    h = Harness(dut, "REQ-01")
    await h.start()
    for _ in range(3):
        await h.cycle(req=0b0110)
    exp = await h.cycle(req=0b1111, rst=1)
    assert exp["grant"] == 0
    exp = await h.cycle(req=0b1111)
    assert exp["grant"] == 0b0001


@cocotb.test()
async def test_single_requester(dut):
    """REQ-02: a lone requester is granted at the next edge, every cycle it asks."""
    h = Harness(dut, "REQ-02")
    await h.start()
    for i in range(N):
        for _ in range(3):
            exp = await h.cycle(req=1 << i)
            assert exp["grant"] == 1 << i


@cocotb.test()
async def test_no_request_no_grant(dut):
    """REQ-04: with no request the grant drops to zero, and priority is kept."""
    h = Harness(dut, "REQ-04")
    await h.start()
    await h.cycle(req=0b0100)
    for _ in range(3):
        exp = await h.cycle(req=0)
        assert exp["grant"] == 0
    exp = await h.cycle(req=0b1111)
    assert exp["grant"] == 0b1000


@cocotb.test()
async def test_round_robin_all(dut):
    """REQ-05: all four requesting: grants rotate 0, 1, 2, 3, 0, ..."""
    h = Harness(dut, "REQ-05")
    await h.start()
    for n in range(12):
        exp = await h.cycle(req=0b1111)
        assert exp["grant"] == 1 << (n % N)


@cocotb.test()
async def test_rotation_skips_idle(dut):
    """REQ-05: the search starts after the last winner and skips idle requesters."""
    h = Harness(dut, "REQ-05")
    await h.start()
    for req in (0b1010, 0b1010, 0b1010, 0b0011, 0b1001, 0b1001, 0b0101, 0b0110):
        await h.cycle(req=req)


@cocotb.test()
async def test_fairness_persistent(dut):
    """REQ-06: a request held high is granted within 4 cycles, whatever the others do."""
    h = Harness(dut, "REQ-06")
    rng = random.Random(0xFA1)
    await h.start()
    for hold in range(N):
        for _ in range(40):
            await h.cycle(req=(1 << hold) | rng.randint(0, 15))


@cocotb.test()
async def test_one_hot(dut):
    """REQ-03: every request pattern gives a one-hot grant or none."""
    h = Harness(dut, "REQ-03")
    await h.start()
    for _ in range(2):
        for req in range(16):
            await h.cycle(req=req)


@cocotb.test()
async def test_random_regression(dut):
    """REQ-01..06: 3000 random cycles with occasional reset, fixed seed."""
    h = Harness(dut, "REQ-01..06")
    rng = random.Random(0xA4B)
    await h.start()
    for _ in range(3000):
        await h.cycle(req=rng.randint(0, 15), rst=int(rng.random() < 0.01))
