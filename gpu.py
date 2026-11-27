"""The GPU baseline: a Permacast model run with PyTorch on a GPU.

python gpu.py model.pc [streams]    prints the steps per second of each stream

It runs copies of the model side by side, the streams, each with a seed of
its own, and checks the first against the reference. One stream is what a
chip does; many show what a GPU does best. Every step is one CUDA graph.

A matrix product runs in 32-bit floats when the bounds show that every sum is
exact in them, and in 64-bit floats otherwise. The random generator is a
linear map on the 32 bits of its state, so all the numbers of a step come
from one product with its powers.
"""
import sys
import time

import numpy as np
import torch

from ref import STEP, Model

torch.backends.cuda.matmul.allow_tf32 = False  # TF32 would round


def xorshift(s):
    s ^= s << 13 & 0xFFFFFFFF
    s ^= s >> 17
    return s ^ (s << 5 & 0xFFFFFFFF)


def powers(n):
    """The bits of the generator after 1 to n draws, as a linear map of its
    bits before: column 32*d + b gives bit b after d + 1 draws."""
    step = np.array([[xorshift(1 << i) >> b & 1 for b in range(32)] for i in range(32)])
    p, out = np.eye(32, dtype=np.int64), []
    for _ in range(n):
        p = p @ step % 2
        out.append(p)
    return np.concatenate(out, 1) if out else np.zeros((32, 0), np.int64)


class Streams:
    """Copies of a model, run side by side on a GPU."""

    def __init__(self, text, streams, device='cuda'):
        self.m = m = Model(text)
        self.device = device
        self.const = {n: torch.tensor(c, device=device) for n, c in m.const.items()}
        self.float = {}  # each matrix of a product, in a float type whose sums are exact
        for _, op, args in m.code:
            if op == 'matmul':
                a, b = args
                biggest = (np.abs(m.const[a]).sum(1) * max(map(abs, m.range[b]))).max()
                self.float[a] = self.const[a].to(torch.float32 if biggest < 2**24 else torch.float64).T
        self.powers = torch.tensor(powers(sum(n for n, _ in m.rand.values())), dtype=torch.float32, device=device)
        seeds = np.arange(1, streams + 1, dtype=np.int64)  # the first stream has the seed of the reference
        self.seeds = torch.tensor(seeds[:, None] >> np.arange(32) & 1, dtype=torch.float32, device=device)
        self.bits = self.seeds.clone()
        self.state = {h: torch.zeros(streams, len(s), dtype=torch.long, device=device) for h, s in m.state.items()}
        self.x = torch.zeros(streams, dtype=torch.long, device=device)

    def reset(self):
        """Back to before the first step, in place, as a CUDA graph needs."""
        self.bits.copy_(self.seeds)
        for h in self.state.values():
            h.zero_()

    def step(self):
        m, v = self.m, {**self.const, **self.state, self.m.input: self.x}
        drawn = (self.bits @ self.powers % 2).view(len(self.x), -1, 32)
        first = 0
        for y, (n, b) in m.rand.items():
            top = drawn[:, first:first + n, 32 - b:].long()
            v[y] = (top << torch.arange(b, device=self.device)).sum(-1)
            first += n
        if first:
            self.bits.copy_(drawn[:, -1])
        for y, op, args in m.code:
            if op == 'matmul':
                w = self.float[args[0]]
                v[y] = (v[args[1]].to(w.dtype) @ w).long()
            elif op == 'argmax':
                v[y] = v[args[0]].argmax(-1, keepdim=True)
            else:  # the reference's own operations work on a batch of vectors
                v[y] = STEP[op](v, *args)
        for h, a in m.next.items():
            self.state[h].copy_(v[a])
        return v[m.output]


def speed(text, steps, streams=1):
    """The steps per second of each stream, after checking the first against the reference."""
    s = Streams(text, streams)
    inputs = torch.arange(steps, device=s.device) * 7 % (s.m.range[s.m.input][1] + 1)
    side = torch.cuda.Stream()
    side.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(side):  # warm up before capture, as CUDA graphs need
        s.step()
    torch.cuda.current_stream().wait_stream(side)
    s.reset()
    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph):  # records the step without running it
        out = s.step()
    first = torch.zeros(steps, *out.shape[1:], dtype=torch.long, device=s.device)  # the first stream's outputs
    torch.cuda.synchronize()
    start = time.perf_counter()
    for i in range(steps):
        s.x.fill_(inputs[i])
        graph.replay()
        first[i].copy_(out[0])
    torch.cuda.synchronize()
    seconds = time.perf_counter() - start
    reference = Model(text)
    for x, y in zip(inputs.tolist(), first.cpu().numpy()):
        assert (reference.step(x) == y).all(), 'the GPU differs from the reference'
    return steps / seconds


if __name__ == '__main__':
    print(f'{speed(open(sys.argv[1]).read(), 2000, *map(int, sys.argv[2:])):,.0f} steps per second')
