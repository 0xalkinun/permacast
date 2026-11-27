"""Tests for ref.py, built on the example in SPEC.md. Run: python test.py"""
from pathlib import Path

from ref import Model

EXAMPLE = Path(__file__).with_name('SPEC.md').read_text().split('```')[1]

# Outputs and bounds worked out by hand.
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

print('ok')
