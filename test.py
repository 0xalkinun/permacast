"""Tests for ref.py and compile.py. Run: python test.py

The hardware tests need Verilator.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from ref import Model

ROOT = Path(__file__).parent
EXAMPLE = (ROOT / 'SPEC.md').read_text().split('```')[1]

# The reference: outputs and bounds worked out by hand.
model = Model(EXAMPLE)
for x, y in [(0, [4, -2]), (1, [-4, 3]), (1, [-4, 1])]:
    assert model.step(x).tolist() == y
assert model.range['r'] == (-8, 8)
assert model.range['m'] == (-42, 39)
assert model.range['d'] == (-8, 8)

# Each change to the example must make it invalid.
INVALID = [
    ('permacast 0', 'permacast 1'),
    ('in x 2', 'in x 3'),                       # no row of E for input 2
    ('const g 2\n3 1', 'const g 3\n3 1 1'),     # sizes differ
    ('const g 2\n3 1', 'const g 2\n3 one'),     # not an integer
    ('const g 2\n3 1', 'const g 2\n3 999999999'),  # m can leave 32 bits
    ('clamp c s -4 4', 'clamp c s -5 4'),       # c can leave the range of h
    ('sub d c h', 'sub d c q'),                 # q is not defined
    ('sub d c h', 'sub d.1 c h'),               # d.1 is not a name
    ('sub d c h', 'sub c c h'),                 # c is already defined
    ('sub d c h', 'neg d c'),                   # unknown operation
    ('next h c\n', ''),                         # h has no next
    ('out d\n', ''),                            # no out
]
for old, new in INVALID:
    assert old in EXAMPLE, old
    try:
        Model(EXAMPLE.replace(old, new))
    except ValueError:
        continue
    raise AssertionError(f'accepted: {new!r}')


def reference(text, data):
    """The output of a model for each input, a line per step."""
    model = Model(text)
    return ''.join(' '.join(map(str, model.step(x))) + '\n' for x in data)


def hardware(text, data):
    """The same, from the compiled model simulated by Verilator."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'model.pc').write_text(text)
        Path(tmp, 'in').write_bytes(bytes(data))
        for command in (
            [sys.executable, ROOT / 'compile.py', 'model.pc', '.'],
            ['verilator', '--binary', '-Wno-WIDTHEXPAND', '-j', '0', '--top', 'tb',
             ROOT / 'tb.v', 'permacast.v', '--Mdir', 'obj', '-o', 'sim'],
            ['./obj/sim', '+in=in', '+out=out'],
        ):
            subprocess.run(command, cwd=tmp, check=True, capture_output=True)
        return Path(tmp, 'out').read_text()


def random_model(rng):
    """A model of random sizes and constants that uses every operation."""
    i, m, n = (int(v) for v in rng.integers(1, 6, 3))

    def const(name, *shape):
        high = int(rng.choice([1, 9, 100]))
        rows = rng.integers(-high, high + 1, shape).reshape(-1, shape[-1]).tolist()
        return [f'const {name} ' + ' '.join(map(str, shape))] + [' '.join(map(str, r)) for r in rows]

    return '\n'.join([
        'permacast 0', f'in x {i}', f'state h {n} -100 100', f'state o {m} -9 9',
        *const('E', i, m), *const('W', n, m), *const('U', n, n), *const('b', n), *const('V', m, n),
        'row e E x', 'matmul p W e', 'matmul q U h', 'add s p q', 'mul t s b', 'shr u t 3',
        'sub v u h', 'clamp w v -100 100', 'next h w', 'matmul y V w', 'mul z y o', 'shr f z 2',
        'clamp c f -9 9', 'next o c', f'out {rng.choice(["y", "o", "e"])}',
    ]) + '\n', rng.integers(0, i, 20).tolist()


# The hardware must agree with the reference on every output.
rng = np.random.default_rng(0)
for text, data in [(EXAMPLE, [0, 1, 1])] + [random_model(rng) for _ in range(4)]:
    assert hardware(text, data) == reference(text, data), text

print('ok')
