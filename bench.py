"""Measure the chips the compiler makes, against the CPU and GPU baselines.

python bench.py model.pc ... [--lanes 1 8 32] [--valid text]    writes BENCH.md

Each model is scored on held-out text, if given, and compiled once for each
number of lanes. A circuit is measured
only if it matches the reference. Its clock ticks per step come from
simulation, and its size and fastest clock from building it for a Lattice
ECP5 with open tools, which anyone can repeat. The baselines must match the
reference too.

It needs a C compiler, PyTorch with a GPU, Verilator, Yosys and nextpnr-ecp5.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import textwrap
from concurrent.futures import ProcessPoolExecutor
from math import prod
from pathlib import Path

import numpy as np
import torch

import gpu
import train
from compile import bits
from ref import Model

ROOT = Path(__file__).parent
STEPS = 10000  # steps timed on the CPU
STREAMS = 1024  # streams run side by side on the GPU
BUILDS = 6  # chips built at once, each of which can take a few gigabytes of memory


def run(*command, cwd=None):
    """Run a tool and return everything it prints."""
    return subprocess.run(command, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def version(tool, flag):
    return re.search(r'\d+\.\d+(\.\d+)?', run(tool, flag)).group()


def processor():
    name = re.search(r'model name\s*: (.*)', Path('/proc/cpuinfo').read_text()).group(1)
    return name.replace('(R)', '').replace('(TM)', '')


def outputs(text, data):
    """What the reference prints for a model."""
    model = Model(text)
    return ''.join(' '.join(map(str, model.step(x))) + '\n' for x in data)


def inputs(model, n):
    return bytes(i * 7 % min(256, model.range[model.input][1] + 1) for i in range(n))


def measure_model(path, valid):
    """The memory of a model, its bits per byte on the held-out text, and the
    steps per second of the baselines."""
    text = path.read_text()
    model = Model(text)
    data = inputs(model, STEPS)
    with tempfile.TemporaryDirectory() as tmp:
        run('cc', '-O3', '-march=native', '-fwrapv', '-o', 'cpu', ROOT / 'cpu.c', cwd=tmp)
        speeds = []
        for _ in range(3):
            result = subprocess.run(['./cpu', path.resolve()], cwd=tmp, input=data, capture_output=True, check=True)
            assert result.stdout.decode() == outputs(text, data), f'{path}: the CPU differs from the reference'
            speeds.append(int(result.stderr.split()[0]))

    def stored(constant):
        """The bits in the constants, or in every other vector."""
        return sum(prod(model.shape[n]) * bits(*model.range[n])
                   for n in model.shape if n != model.input and (n in model.const) == constant)

    alone, together = gpu.speed(text, 2000), gpu.speed(text, 200, STREAMS) * STREAMS
    quality = f'{train.evaluate(text, np.fromfile(valid, np.uint8)):.3f}' if valid else ''
    return [path.stem, hashlib.sha256(text.encode()).hexdigest()[:12], f'{stored(True):,}', f'{stored(False):,}',
            quality, *(f'{round(n):,}' for n in (max(speeds), alone, together))]


def measure_chip(path, lanes):
    """The speed and size of a model's chip."""
    text = path.read_text()
    data = inputs(Model(text), 8)
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'in').write_bytes(data)
        run(sys.executable, ROOT / 'compile.py', path.resolve(), '.', str(lanes), cwd=tmp)
        run('verilator', '--binary', '-Wno-WIDTHEXPAND', '-j', '0', '--top', 'tb', ROOT / 'tb.v',
            'permacast.v', '--Mdir', 'obj', '-o', 'sim', cwd=tmp)
        ticks = int(run('./obj/sim', '+in=in', '+out=out', cwd=tmp).split()[0])
        assert Path(tmp, 'out').read_text() == outputs(text, data), f'{path}: the chip differs from the reference'
        run('yosys', '-q', '-p', 'read_verilog permacast.v; synth_ecp5 -top permacast -json synth.json', cwd=tmp)
        try:
            run('nextpnr-ecp5', '--85k', '--package', 'CABGA381', '--json', 'synth.json', '--seed', '1',
                '--lpf-allow-unconstrained', '--timing-allow-fail', '--report', 'report.json', cwd=tmp)
        except subprocess.CalledProcessError as e:
            if 'no BELs remaining' not in e.stdout:
                raise
            return [path.stem, lanes, f'{ticks:,}', 'does not fit']
        report = json.loads(Path(tmp, 'report.json').read_text())
    (clock,) = (c['achieved'] for c in report['fmax'].values())
    cells = [report['utilization'][c]['used'] for c in ('TRELLIS_COMB', 'TRELLIS_FF', 'DP16KD', 'MULT18X18D')]
    return [path.stem, lanes, f'{ticks:,}', f'{clock:.1f}', f'{round(clock * 1e6 / ticks):,}', *(f'{n:,}' for n in cells)]


def table(columns, rows):
    rows = [row + [''] * (len(columns) - len(row)) for row in rows]
    return ''.join('| ' + ' | '.join(map(str, row)) + ' |\n' for row in [columns, ['---'] * len(columns), *rows])


def paragraph(text, indent=''):
    return textwrap.fill(text, 79, subsequent_indent=indent) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('models', nargs='+', type=Path)
    parser.add_argument('--lanes', nargs='+', type=int, default=[1, 8, 32])
    parser.add_argument('--valid', type=Path, help='held-out text to score the models on')
    args = parser.parse_args()
    models = [measure_model(p, args.valid) for p in args.models]  # one at a time, since they are timed
    with ProcessPoolExecutor(BUILDS) as pool:
        chips = list(pool.map(measure_chip, *zip(*[(p, lanes) for p in args.models for lanes in args.lanes])))
    (ROOT / 'BENCH.md').write_text(
        '# Bench\n\n'
        + paragraph('What the compiler makes of each model, written by `python bench.py`. Every chip and '
                    'every CPU run here matches the reference exactly.')
        + '\n## Models\n\n'
        + paragraph('- **ROM and RAM bits** are the memory the model declares: its constants, and every '
                    'other vector.', '  ')
        + (paragraph(f'- **Bits per byte** are the cross-entropy of the next byte on {args.valid.name}, in its '
                     f'first 2,048 windows of {train.TIME} bytes, each begun from zero state. Lower is '
                     'better.', '  ') if args.valid else '')
        + paragraph(f"- **CPU steps per second** are for `cpu.c` built with GCC {version('cc', '--version')}, "
                    f'on one core of the {processor()}, the best of three runs of {STEPS:,} steps.', '  ')
        + paragraph(f'- **GPU steps per second** are for `gpu.py` with PyTorch {torch.__version__.split("+")[0]} on '
                    f'an {torch.cuda.get_device_name()}: one stream, and {STREAMS:,} streams together.', '  ')
        + '\n' + table(['Model', 'SHA-256', 'ROM, bits', 'RAM, bits', 'Bits per byte', 'CPU steps per second',
                        'GPU steps per second', f'GPU, {STREAMS:,} streams'], models)
        + '\n## Chips\n\n'
        + paragraph(f"- **Ticks per step** are counted in simulation with Verilator "
                    f"{version('verilator', '--version')}.", '  ')
        + paragraph('- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a Lattice '
                    f"ECP5-85F, built with Yosys {version('yosys', '-V')} and nextpnr "
                    f"{version('nextpnr-ecp5', '--version')} at seed 1.", '  ')
        + '\n' + table(['Model', 'Lanes', 'Ticks per step', 'Clock, MHz', 'Steps per second', 'Logic cells',
                        'Flip-flops', 'Block RAMs', 'Multipliers'], chips))
