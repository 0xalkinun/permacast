"""Reference interpreter for Permacast models: SPEC.md in executable form.

python ref.py model.pc [seed] < input    prints the output of each step, a line each
"""
import re
import sys
from itertools import islice

import numpy as np

LIMIT = 2**31  # the bounds of every value must lie within [-LIMIT, LIMIT)

STEP = {
    'row': lambda v, m, x: v[m][v[x]],
    'matmul': lambda v, m, a: v[m] @ v[a],
    'add': lambda v, a, b: v[a] + v[b],
    'sub': lambda v, a, b: v[a] - v[b],
    'mul': lambda v, a, b: v[a] * v[b],
    'shr': lambda v, a, k: v[a] >> k,
    'clamp': lambda v, a, lo, hi: v[a].clip(lo, hi),
    'take': lambda v, t, a: v[t][v[a]],
    'argmax': lambda v, a: v[a].argmax(keepdims=True),
}


def check(ok, why):
    if not ok:
        raise ValueError(why)


def token(t):
    if re.fullmatch('-?[0-9]+', t):
        return int(t)
    check(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', t), f'{t}: not an integer or a name')
    return t


class Model:
    """A validated model. step(x) takes one input and returns the output vector."""

    def __init__(self, text, seed=1):
        lines = (line.split('#')[0].split() for line in text.splitlines())
        lines = ([token(t) for t in line] for line in lines if line)
        check(next(lines, None) == ['permacast', 0], 'missing header "permacast 0"')
        self.const = {}  # name -> array
        self.state = {}  # name -> array, zero before the first step
        self.rand = {}   # name -> (size, bits) of a random vector
        self.code = []   # (name, operation, arguments) in file order
        self.next = {}   # state -> the value it takes after each step
        self.shape = {}  # name -> shape, () for the input
        self.range = {}  # name -> (lo, hi), bounds that hold on every step
        self.input = self.output = None
        self.random = seed  # the random generator
        self.values = {}    # name -> array, every value of the last step
        check(0 <= seed < 2**32, 'seed out of range')
        for line in lines:
            try:
                self._line(lines, *line)
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f'{" ".join(map(str, line))}: {e!r}') from None
        check(self.input and self.output, 'a model needs one in and one out')
        check(self.next.keys() == self.state.keys(), 'every state needs a next')

    def _line(self, lines, op, name, *args):
        shape, rng = self.shape, self.range
        if op == 'out':
            check(self.output is None, 'only one out')
            check(len(shape[name]) == 1, 'needs a vector')
            self.output = name
        elif op == 'next':
            a, = args
            (lo, hi), (low, high) = rng[a], rng[name]
            check(name in self.state and name not in self.next, 'needs a state without a next')
            check(shape[a] == shape[name], 'size differs from the state')
            check(low <= lo and hi <= high, 'can leave the range of the state')
            self.next[name] = a
        else:
            check(isinstance(name, str) and name not in shape, 'needs a new name')
            shape[name], rng[name] = self._value(lines, op, name, *args)
            lo, hi = rng[name]
            check(-LIMIT <= lo <= hi < LIMIT, 'can leave 32 bits')

    def _value(self, lines, op, name, *args):
        """Create the value `name` and return its shape and bounds."""
        shape, rng = self.shape, self.range
        if op == 'in':
            check(self.input is None, 'only one in')
            self.input = name
            n, = args
            return (), (0, n - 1)
        if op == 'state':
            n, lo, hi = args
            check(lo <= 0 <= hi, 'range must include zero')
            self.state[name] = np.zeros(n, np.int64)
            return (n,), (lo, hi)
        if op == 'const':
            rows = list(islice(lines, args[0] if len(args) == 2 else 1))
            c = self.const[name] = np.array(rows, np.int64).reshape(args)
            return args, (int(c.min()), int(c.max()))
        if op == 'rand':
            n, b = args
            check(n > 0 and b > 0, 'needs a size and a number of bits')
            self.rand[name] = n, b
            return (n,), (0, 2**b - 1)
        check(op in STEP, 'unknown operation')
        self.code.append((name, op, args))
        if op in ('row', 'matmul'):
            m, a = args
            check(m in self.const and len(shape[m]) == 2, 'needs a constant matrix')
            if op == 'row':
                check(a == self.input and rng[a][1] < shape[m][0], 'needs a row for every input')
                return shape[m][1:], rng[m]
            check(shape[a] == shape[m][1:], 'sizes differ')
            lo, hi = rng[a]
            pos = self.const[m].clip(min=0).sum(1).tolist()
            neg = self.const[m].clip(max=0).sum(1).tolist()
            return shape[m][:1], (min(p * lo + n * hi for p, n in zip(pos, neg)),
                                  max(p * hi + n * lo for p, n in zip(pos, neg)))
        if op == 'take':
            t, a = args
            check(len(shape[t]) == len(shape[a]) == 1, 'needs two vectors')
            check(0 <= rng[a][0] and rng[a][1] < shape[t][0], 'index can leave the table')
            return shape[a], rng[t]
        a, *rest = args
        lo, hi = rng[a]
        check(len(shape[a]) == 1, 'needs a vector')
        if op == 'argmax':
            check(not rest, 'takes one vector')
            return (1,), (0, shape[a][0] - 1)
        if op == 'shr':
            k, = rest
            check(k >= 0, 'shift must not be negative')
            return shape[a], (lo >> k, hi >> k)
        if op == 'clamp':
            low, high = rest
            check(low <= high, 'empty range')
            return shape[a], (min(max(lo, low), high), min(max(hi, low), high))
        b, = rest
        check(shape[a] == shape[b], 'sizes differ')
        if op == 'add':
            return shape[a], (lo + rng[b][0], hi + rng[b][1])
        if op == 'sub':
            return shape[a], (lo - rng[b][1], hi - rng[b][0])
        ends = [x * y for x in rng[a] for y in rng[b]]
        return shape[a], (min(ends), max(ends))

    def _random(self, n, b):
        """n numbers of b bits each from the generator, which is xorshift32."""
        numbers = []
        for _ in range(n):
            self.random ^= self.random << 13 & 0xFFFFFFFF
            self.random ^= self.random >> 17
            self.random ^= self.random << 5 & 0xFFFFFFFF
            numbers.append(self.random >> 32 - b)
        return np.array(numbers)

    def step(self, x):
        check(0 <= x <= self.range[self.input][1], 'input out of range')
        v = self.values = {**self.const, **self.state, self.input: x}
        for name, (n, b) in self.rand.items():
            v[name] = self._random(n, b)
        for name, op, args in self.code:
            v[name] = STEP[op](v, *args)
        self.state = {h: v[a] for h, a in self.next.items()}
        return v[self.output]


if __name__ == '__main__':
    model = Model(open(sys.argv[1]).read(), *map(int, sys.argv[2:]))
    for x in sys.stdin.buffer.read():
        print(*model.step(x))
