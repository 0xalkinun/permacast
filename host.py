"""Let a chip write on its serial port, and check every byte it sends.

python host.py port model.pc [seed] [bytes]    e.g. port /dev/ttyUSB1

Reset the chip first. The host sends it the seed, then a zero byte, then each
byte the chip answers with, so the chip writes as it does on its own. Each
answer is printed, and checked against the reference. The port is set to
115200 baud with stty.
"""
import subprocess
import sys

from ref import Model

port, path, *rest = sys.argv[1:]
seed, count = (int(a) for a in rest + ['1', '-1'][len(rest):])
model = Model(open(path).read(), seed)
subprocess.run(['stty', '-f' if sys.platform == 'darwin' else '-F', port, '115200', 'raw', '-echo'], check=True)
with open(port, 'r+b', buffering=0) as chip:
    chip.write(seed.to_bytes(4, 'little'))
    x = 0
    while count:
        chip.write(bytes([x]))
        x, expected = chip.read(1)[0], int(model.step(x)[0])
        if x != expected:
            sys.exit(f'\nthe chip sent {x} where the reference sends {expected}')
        sys.stdout.buffer.write(bytes([x]))
        sys.stdout.flush()
        count -= 1
