"""Bit-accurate Python reference model of sat_gain (blocks/sat_gain/spec.md).

Integers only, no floating point: the product of two Q1.7 codes is a Q2.14
code; shifting right by 7 with Python's floor shift is exactly the hardware's
truncation toward minus infinity; the result is then clamped to the Q1.7
range [-128, 127] and `sat` says whether the clamp changed it.

step() takes the inputs sampled at a rising clock edge and returns the
outputs as they must read just after that edge.
"""

QMIN, QMAX = -128, 127


def to_signed8(v: int) -> int:
    v &= 0xFF
    return v - 256 if v & 0x80 else v


def sat_gain(x: int, g: int) -> tuple[int, int]:
    """(y, sat) for signed 8-bit codes x, g in [-128, 127]."""
    t = (x * g) >> 7  # floor shift == truncation toward -inf
    if t > QMAX:
        return QMAX, 1
    if t < QMIN:
        return QMIN, 1
    return t, 0


class SatGainModel:
    def __init__(self):
        self.reset()

    def reset(self):
        self.y, self.sat = 0, 0

    def outputs(self):
        return {"y": self.y & 0xFF, "sat": self.sat}

    def step(self, x, g, rst=0):
        if rst:
            self.reset()
        else:
            self.y, self.sat = sat_gain(to_signed8(x), to_signed8(g))
        return self.outputs()
