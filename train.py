"""Train a Permacast model and export it.

python train.py train.txt valid.txt model.pc

A model is a program in the format of SPEC.md whose constants are learned.
Training runs that program on floats that hold exact integers, so the exported
file computes what was trained. The reference then confirms it, bit for bit.

The program gives every byte a score. The exported model ends by choosing a
byte at random, the likeliest most often.
"""
import argparse
import math

import numpy as np
import torch
import torch.nn.functional as F

from ref import Model

SCALE = 256  # the loss reads the scores as logits in units of 1/SCALE
BATCH, TIME, RATE = 128, 256, 1e-2
TEMPERATURE = 0.7  # below 1, the exported model favours the likeliest bytes more

# Adding Gumbel noise to the scores and taking the largest chooses byte i with
# probability proportional to exp(y[i] / (SCALE * TEMPERATURE)).
GUMBEL = np.round(-np.log(-np.log((np.arange(256) + 0.5) / 256)) * SCALE * TEMPERATURE).astype(int)
CHOOSE = '''\
rand roll 256 8
take noise GUMBEL roll
add noisy y noise
argmax choice noisy
out choice
'''


def ste(x, y):
    """The value of y with the gradient of x."""
    return x + (y - x).detach()


STEP = {  # the operations of ref.py, on batches of vectors
    'row': lambda v, m, x: v[m][v[x]],
    'matmul': lambda v, m, a: v[a] @ v[m].T,
    'add': lambda v, a, b: v[a] + v[b],
    'sub': lambda v, a, b: v[a] - v[b],
    'mul': lambda v, a, b: v[a] * v[b],
    'shr': lambda v, a, k: ste(v[a] / 2**k, (v[a] / 2**k).floor()),
    'clamp': lambda v, a, lo, hi: v[a].clamp(lo, hi),
}


def gru(n, levels=1, loops=1, m=64):
    """A gated recurrent model with n units, whose weights are integers from
    -levels to levels. Its cell runs loops times on each byte, with the same
    weights.

    Returns its constants as {name: (scale, start)} and the program that uses
    them, which leaves the score of every byte in y. A constant is learned as
    a tensor within -1 to 1, beginning at start, and is that tensor times
    scale, rounded. Every weight begins at -1, 0 or 1, whatever the levels.
    """
    def rand(*shape):
        return torch.rand(shape) * 2 - 1

    def weights(*shape):
        return levels, rand(*shape) / levels

    k = 3 + levels.bit_length()  # the shift that brings a sum back to the range of the state
    consts = {
        'E': (127, rand(256, m)),
        'Wz': weights(n, m), 'Uz': weights(n, n), 'bz': (127 << k, torch.full((n,), 0.5)),
        'Wc': weights(n, m), 'Uc': weights(n, n), 'bc': (127 << k, torch.zeros(n)),
        'Wy': weights(256, n),
    }
    program = f'''\
in x 256
state h {n} -127 127
row e E x
matmul zx Wz e       # z: how much of each unit to replace, 0 to 128
matmul cx Wc e       # c: the candidate state
'''
    for i in range(1, loops + 1):  # each run of the cell moves the state from h to h1, h1 to h2, ...
        h = f'h{i - 1}' if i > 1 else 'h'
        program += f'''\
matmul zh{i} Uz {h}
add za{i} zx zh{i}
add zb{i} za{i} bz
shr zc{i} zb{i} {k}
clamp z{i} zc{i} 0 128
matmul ch{i} Uc {h}
add ca{i} cx ch{i}
add cb{i} ca{i} bc
shr cc{i} cb{i} {k}
clamp c{i} cc{i} -127 127
sub d{i} c{i} {h}            # h moves z/128 of the way to c
mul u{i} z{i} d{i}
shr s{i} u{i} 7
add t{i} {h} s{i}
clamp h{i} t{i} -127 127
'''
    program += f'''\
next h h{loops}
matmul y Wy h{loops}
'''
    return consts, program


def export(consts, program):
    """The text of a model, from integer constants and a program."""
    lines = ['permacast 0']
    for name, c in consts.items():
        lines.append(' '.join(map(str, ('const', name, *c.shape))))
        lines += (' '.join(map(str, row)) for row in c.reshape(-1, c.shape[-1]).tolist())
    return '\n'.join(lines) + '\n' + program


def run(model, consts, x):
    """Run a model from zero state on a batch of input sequences.

    x is (batch, time). Returns the outputs, (batch, time, size).
    """
    state = {h: x.new_zeros(len(x), len(s), dtype=torch.float) for h, s in model.state.items()}
    outs = []
    for t in range(x.shape[1]):
        v = {**consts, **state, model.input: x[:, t]}
        for name, op, args in model.code:
            v[name] = STEP[op](v, *args)
        state = {h: v[a] for h, a in model.next.items()}
        outs.append(v[model.output])
    return torch.stack(outs, 1)


def evaluate(text, data, windows=2048, device='cuda'):
    """The bits per byte of an exported model on the first windows of the data,
    each TIME bytes long and begun from zero state."""
    model = Model(text.replace(CHOOSE, 'out y\n'))
    consts = {n: torch.tensor(c, dtype=torch.float, device=device) for n, c in model.const.items()}
    x = torch.from_numpy(data[:windows * (TIME + 1)].reshape(windows, TIME + 1).copy()).long()
    total = 0
    with torch.no_grad():
        for batch in x.split(256):
            batch = batch.to(device)
            y = run(model, consts, batch[:, :-1])
            total += F.cross_entropy(y.flatten(0, 1) / SCALE, batch[:, 1:].flatten(), reduction='sum').item()
    return total / (windows * TIME) / math.log(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('train')
    parser.add_argument('valid')
    parser.add_argument('out')
    parser.add_argument('--steps', type=int, default=20000)
    parser.add_argument('--units', type=int, default=512)
    parser.add_argument('--levels', type=int, default=1, help='weights are integers from -levels to levels')
    parser.add_argument('--loops', type=int, default=1, help='runs of the cell on each byte')
    args = parser.parse_args()

    torch.manual_seed(0)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    train, valid = (torch.from_numpy(np.fromfile(f, np.uint8)) for f in (args.train, args.valid))
    consts, program = gru(args.units, args.levels, args.loops)
    scale = {name: s for name, (s, _) in consts.items()}
    latent = {name: p.to(device).requires_grad_() for name, (_, p) in consts.items()}

    def quantized():
        return {name: ste(p * scale[name], (p * scale[name]).round()) for name, p in latent.items()}

    def text(end, **more):
        consts = {name: c.long().cpu().numpy() for name, c in quantized().items()}
        return export({**consts, **more}, program + end)

    def loss(data):
        """Bits per byte on random windows of the data."""
        i = torch.randint(len(data) - TIME, (BATCH, 1)) + torch.arange(TIME + 1)
        x = data[i].to(device).long()
        y = run(model, quantized(), x[:, :-1])
        return F.cross_entropy(y.flatten(0, 1) / SCALE, x[:, 1:].flatten()) / math.log(2)

    model = Model(text('out y\n'))  # checks the program before any training
    optimizer = torch.optim.Adam(latent.values(), RATE)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, RATE, total_steps=max(args.steps, 1))
    for step in range(args.steps):
        bits = loss(train)
        optimizer.zero_grad()
        bits.backward()
        optimizer.step()
        schedule.step()
        with torch.no_grad():
            for p in latent.values():
                p.clamp_(-1, 1)
            if step % 500 == 0 or step == args.steps - 1:
                held = sum(loss(valid).item() for _ in range(10)) / 10
                print(f'step {step}: train {bits.item():.3f}, valid {held:.3f} bits per byte', flush=True)

    with open(args.out, 'w') as f:
        f.write(text(CHOOSE, GUMBEL=GUMBEL))

    # The reference must agree with the trainer on every score.
    reference = Model(open(args.out).read())
    x = valid[:1000]
    with torch.no_grad():
        trained = run(model, quantized(), x[None].to(device).long())[0].long().cpu().numpy()
    for b, y in zip(x, trained):
        reference.step(int(b))
        assert (reference.values['y'] == y).all(), 'reference differs'
    print(f'{args.out}: the reference matches the trainer on {len(x)} steps')
    print(f'{evaluate(open(args.out).read(), valid.numpy(), device=device):.4f} bits per byte on held-out text')

    # What the chip writes when left alone: each output is its next input.
    reference, x, story = Model(open(args.out).read()), 0, bytearray()
    for _ in range(500):
        x = int(reference.step(x)[0])
        story.append(x)
    print(story.decode(errors='replace'))


if __name__ == '__main__':
    main()
