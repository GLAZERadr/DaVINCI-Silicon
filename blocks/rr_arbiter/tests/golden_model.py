"""Cycle-accurate Python reference model of rr_arbiter (blocks/rr_arbiter/spec.md).

step() takes the inputs sampled at a rising clock edge and returns the
outputs as they must read just after that edge.
"""

N = 4


class ArbiterModel:
    def __init__(self):
        self.reset()

    def reset(self):
        self.grant = 0
        self.ptr = 0  # requester with the highest priority at the next edge

    def outputs(self):
        return {"grant": self.grant}

    def step(self, req, rst=0):
        if rst:
            self.reset()
            return self.outputs()
        for k in range(N):
            i = (self.ptr + k) % N
            if req >> i & 1:
                self.grant = 1 << i
                self.ptr = (i + 1) % N
                break
        else:
            self.grant = 0  # no request, no grant; priority unchanged
        return self.outputs()
