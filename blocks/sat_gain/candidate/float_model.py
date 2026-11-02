"""Naive floating-point model of sat_gain: the kind of reference model that is
written first, from the maths rather than from the hardware rules.

It converts the Q1.7 codes to floats, multiplies, rounds to the nearest code
and stores the result in 8 bits the way a C cast to int8 would (wraps). So it
differs from the spec twice: it rounds where the hardware truncates, and it
wraps where the hardware saturates. It has no `sat` output.

Deliberately wrong. Used only by the S3 demo (verify/model_demo.py) and the
candidate tests next to it; the frozen suite uses tests/golden_model.py.
"""
import math


def float_gain(x: int, g: int) -> int:
    """y code (signed, -128..127) for signed 8-bit codes x, g."""
    v = (x / 128.0) * (g / 128.0)
    q = math.floor(v * 128.0 + 0.5)  # round to nearest, ties up
    q &= 0xFF  # int8 cast: wraps instead of saturating
    return q - 256 if q & 0x80 else q


class FloatGainModel:
    def __init__(self):
        self.y = 0

    def step(self, x: int, g: int, rst: int = 0) -> dict:
        def s8(v):
            v &= 0xFF
            return v - 256 if v & 0x80 else v
        self.y = 0 if rst else float_gain(s8(x), s8(g))
        return {"y": self.y & 0xFF}
