"""Tests for the reference, the CPU baseline, the compiler and the chip.

python test.py    needs a C compiler and Verilator
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
    ('out d', 'take t g d\nout d'),             # d can leave the indices of g
    ('out d', 'take t h x\nout d'),             # h is not a constant
    ('out d', 'rand t 2 32\nout d'),            # t can leave 32 bits
]
for old, new in INVALID:
    assert old in EXAMPLE, old
    try:
        Model(EXAMPLE.replace(old, new))
    except ValueError:
        continue
    raise AssertionError(f'accepted: {new!r}')


BUILD = tempfile.TemporaryDirectory()
subprocess.run(['cc', '-O3', '-march=native', '-fwrapv', '-o', f'{BUILD.name}/cpu', ROOT / 'cpu.c'], check=True)


def cpu(text, data, seed):
    """What the CPU baseline prints for a model."""
    Path(BUILD.name, 'model.pc').write_text(text)
    return subprocess.run([f'{BUILD.name}/cpu', f'{BUILD.name}/model.pc', str(seed)], input=bytes(data),
                          check=True, capture_output=True).stdout.decode()


def simulate(text, bench, data=(), lanes=1, **settings):
    """What a testbench writes when it runs the model, compiled with a number of
    lanes, in Verilator."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'model.pc').write_text(text)
        Path(tmp, 'in').write_bytes(bytes(data))
        for command in (
            [sys.executable, ROOT / 'compile.py', 'model.pc', '.', str(lanes)],
            ['verilator', '--binary', '-Wno-WIDTHEXPAND', '-j', '0', '--top', bench[0][:-2],
             *(ROOT / f for f in bench), 'permacast.v', '--Mdir', 'obj', '-o', 'sim'],
            ['./obj/sim', '+in=in', '+out=out', *(f'+{k}={v}' for k, v in settings.items())],
        ):
            result = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            assert result.returncode == 0, (command, result.returncode, result.stdout + result.stderr)
        return Path(tmp, 'out').read_text()


def random_model(rng, out=None):
    """A model of random sizes and constants that uses every operation."""
    i, m, n = (int(v) for v in rng.integers(1, 13, 3))
    if out == 'pick':  # every output must be a valid input
        i = max(i, m)

    def const(name, *shape):
        high = int(rng.choice([1, 9, 100]))
        rows = rng.integers(-high, high + 1, shape).reshape(-1, shape[-1]).tolist()
        return [f'const {name} ' + ' '.join(map(str, shape))] + [' '.join(map(str, r)) for r in rows]

    return '\n'.join([
        'permacast 0', f'in x {i}', f'state h {n} -100 100', f'state o {m} -9 9',
        *const('E', i, m), *const('W', n, m), *const('U', n, n), *const('b', n), *const('V', m, n),
        *const('T', 8), f'rand dice {m} 3', f'rand coin {n} 1',  # coin is never read, but still drawn
        'row e E x', 'matmul p W e', 'matmul q U h', 'add s p q', 'mul t s b', 'shr u t 3',
        'sub v u h', 'clamp w v -100 100', 'next h w', 'matmul y V w', 'take luck T dice',
        'add lucky y luck', 'argmax pick lucky', 'mul z lucky o', 'shr f z 2', 'clamp c f -9 9',
        'next o c', f'out {out or rng.choice(["lucky", "pick", "o", "e"])}',
    ]) + '\n', rng.integers(0, i, 20).tolist(), int(rng.integers(2**32))


# The CPU baseline and the compiled model must agree with the reference on
# every output.
rng = np.random.default_rng(0)
models = [(EXAMPLE, [0, 1, 1], 1)] * 2 + [random_model(rng) for _ in range(10)]
for (text, data, seed), lanes in zip(models, [1, 2, 1, 2, 4, 8] * 2):
    model = Model(text, seed)
    expected = ''.join(' '.join(map(str, model.step(x))) + '\n' for x in data)
    assert cpu(text, data, seed) == expected, text
    assert simulate(text, ['tb.v'], data, lanes, seed=seed) == expected, (lanes, text)

# So must the chip, through its serial port: answering a host, and alone.
CHIP = ['chip_tb.v', 'chip.v']
for (text, data, seed), lanes in zip([random_model(rng, 'pick') for _ in range(3)], [1, 2, 4]):
    model = Model(text, seed)
    expected = ''.join(f'{model.step(x)[0]}\n' for x in data)
    assert simulate(text, CHIP, data, lanes, seed=seed) == expected, text
    taken, *written = simulate(text, CHIP, (), lanes, seed=seed % 1000, loop=20).split()
    model, x = Model(text, int(taken)), 0
    for y in written:
        x = int(model.step(x)[0])
        assert int(y) == x, text
    assert len(written) == 20

print('ok')
