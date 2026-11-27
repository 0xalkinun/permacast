"""Measure the chips the compiler makes.

python bench.py model.pc ...    writes BENCH.md

A circuit is measured only if it matches the reference. Its clock ticks per
step come from simulation. Its size and its fastest clock come from building
it for a Lattice ECP5 with open tools, which anyone can repeat.

It needs Verilator, Yosys and nextpnr-ecp5.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import textwrap
from math import prod
from pathlib import Path

from compile import bits
from ref import Model

ROOT = Path(__file__).parent
COLUMNS = ['Model', 'SHA-256', 'Ticks per step', 'Clock, MHz', 'Steps per second', 'Logic cells',
           'Flip-flops', 'Block RAMs', 'Multipliers', 'ROM, bits', 'RAM, bits']


def run(*command, cwd=None):
    """Run a tool and return everything it prints."""
    return subprocess.run(command, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def version(tool, flag):
    return re.search(r'\d+\.\d+(\.\d+)?', run(tool, flag)).group()


def measure(path):
    """The row of results for a model file."""
    text = path.read_text()
    model = Model(text)
    data = bytes(i * 7 % min(256, model.range[model.input][1] + 1) for i in range(8))
    expected = ''.join(' '.join(map(str, model.step(x))) + '\n' for x in data)
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'in').write_bytes(data)
        run(sys.executable, ROOT / 'compile.py', path.resolve(), '.', cwd=tmp)
        run('verilator', '--binary', '-Wno-WIDTHEXPAND', '-j', '0', '--top', 'tb', ROOT / 'tb.v',
            'permacast.v', '--Mdir', 'obj', '-o', 'sim', cwd=tmp)
        ticks = int(run('./obj/sim', '+in=in', '+out=out', cwd=tmp).split()[0])
        assert Path(tmp, 'out').read_text() == expected, f'{path}: differs from the reference'
        run('yosys', '-q', '-p', 'read_verilog permacast.v; synth_ecp5 -top permacast -json synth.json',
            cwd=tmp)
        run('nextpnr-ecp5', '--85k', '--package', 'CABGA381', '--json', 'synth.json', '--seed', '1',
            '--lpf-allow-unconstrained', '--timing-allow-fail', '--report', 'report.json', cwd=tmp)
        report = json.loads(Path(tmp, 'report.json').read_text())
    (clock,) = (c['achieved'] for c in report['fmax'].values())
    cells = [report['utilization'][c]['used'] for c in ('TRELLIS_COMB', 'TRELLIS_FF', 'DP16KD', 'MULT18X18D')]

    def stored(constant):
        """The bits of memory in the constants, or in every other vector."""
        return sum(prod(model.shape[n]) * bits(*model.range[n])
                   for n in model.shape if n != model.input and (n in model.const) == constant)

    return [path.stem, hashlib.sha256(text.encode()).hexdigest()[:12], f'{ticks:,}', f'{clock:.1f}',
            *(f'{n:,}' for n in (round(clock * 1e6 / ticks), *cells, stored(True), stored(False)))]


if __name__ == '__main__':
    rows = [COLUMNS, ['---'] * len(COLUMNS)] + [measure(Path(p)) for p in sys.argv[1:]]
    notes = [
        'What the compiler makes of each model, written by `python bench.py`. Every circuit here '
        'matches the reference exactly.',
        f"- **Ticks per step** are counted in simulation with Verilator {version('verilator', '--version')}.",
        '- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a Lattice ECP5-85F, '
        f"built with Yosys {version('yosys', '-V')} and nextpnr {version('nextpnr-ecp5', '--version')} "
        'at seed 1.',
        '- **ROM and RAM bits** are the memory the circuit declares, on any target.',
    ]
    (ROOT / 'BENCH.md').write_text(
        '# Bench\n\n' + textwrap.fill(notes[0], 79) + '\n\n'
        + ''.join(textwrap.fill(n, 79, subsequent_indent='  ') + '\n' for n in notes[1:]) + '\n'
        + ''.join('| ' + ' | '.join(row) + ' |\n' for row in rows))
