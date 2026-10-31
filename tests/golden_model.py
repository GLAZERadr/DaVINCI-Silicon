"""Cycle-accurate Python reference model of the sync FIFO (spec/fifo_spec.md).

step() takes the inputs sampled at a rising clock edge and returns the
outputs as they must read just after that edge.
"""
from collections import deque


class FifoModel:
    def __init__(self, width=8, depth=16, af_thresh=14):
        self.width, self.depth, self.af_thresh = width, depth, af_thresh
        self.reset()

    def reset(self):
        self.q = deque()
        self.dout = 0
        self.overflow = 0
        self.underflow = 0

    @property
    def count(self):
        return len(self.q)

    def outputs(self):
        c = self.count
        return {
            "dout": self.dout,
            "count": c,
            "full": int(c == self.depth),
            "empty": int(c == 0),
            "almost_full": int(c >= self.af_thresh),
            "overflow": self.overflow,
            "underflow": self.underflow,
        }

    def step(self, wr_en, din, rd_en, rst=0):
        if rst:
            self.reset()
            return self.outputs()
        full = self.count == self.depth
        empty = self.count == 0
        self.overflow = int(bool(wr_en and full and not rd_en))
        self.underflow = int(bool(rd_en and empty))
        do_read = rd_en and not empty
        do_write = wr_en and (not full or rd_en)
        if do_read:
            self.dout = self.q.popleft()
        if do_write:
            self.q.append(din & ((1 << self.width) - 1))
        return self.outputs()
