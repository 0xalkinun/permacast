"""Compile a Permacast model to Verilog.

python compile.py model.pc out [matrix lanes [vector lanes]]    writes to out

The circuit keeps every constant in a read-only memory and every vector in a
memory of its own, each as wide as the bounds of its values require. It runs
the operations of the model in order. A vector that only elementwise
operations make and read has no memory or operation of its own: each vector
lane computes it in a pipeline of registers, one operation a tick, and the
operation that reads it stores its results as many ticks later.

Its lanes work side by side, in two kinds, each a power of two. Matrix lanes
only multiply and add: each sums a row of a matrix product, a weight a tick,
then hands its sum to the vector lanes, which do everything else and are no
more in number. A word of a vector holds an element for each vector lane, and
every operation takes a tick per word, except the output, which takes a tick
per element.
"""
import sys
from math import prod
from pathlib import Path

import numpy as np

from ref import Model

SIGN = {'add': '+', 'sub': '-', 'mul': '*'}
ELEMENTWISE = ('add', 'sub', 'mul', 'shr', 'clamp')
VECTOR = 4  # vector lanes unless given: more cost much and gain little next to matrix lanes


def bits(lo, hi):
    """The width of a signed number that holds lo to hi."""
    return max(hi, -lo - 1).bit_length() + 1


def index(n):
    """The width of an index into n elements."""
    return max(1, (n - 1).bit_length())


def compile(m, matrix=1, vector=None):
    """The files of the circuit for a model, with its matrix and vector lanes:
    permacast.v and a .hex file per constant."""
    L, V = matrix, vector or min(matrix, VECTOR)
    lv = V.bit_length() - 1
    assert L & L - 1 == 0 and V == 1 << lv and V <= L, 'lanes must be powers of two, with no more vector lanes'
    S = L // V  # the words of a vector that the sums of the matrix lanes fill
    size = {n: prod(s) for n, s in m.shape.items()}

    def words(n, per=V):
        return -(-n // per)

    # A vector that an elementwise operation makes, and only elementwise
    # operations read, has no memory: each lane computes it where it is read.
    inline = {y for y, op, _ in m.code if op in ELEMENTWISE} - {*m.state, *m.next.values(), m.output}
    for y, op, args in m.code:
        if op not in ELEMENTWISE:
            inline -= set(args)

    # How each memory is laid out. A vector holds its elements i*V to i*V + V - 1
    # in word i. A matrix for matmul holds column j of rows g*L to g*L + L - 1 in
    # word g*cols + j. A matrix for row holds each row in words of its own. A
    # table for take holds one element per word.
    layout = {}

    def use(name, how):
        if layout.setdefault(name, how) != how:
            raise NotImplementedError(f'{name} is used in two ways')

    for y, op, args in m.code:
        names = [a for a in args if isinstance(a, str) and a != m.input]
        if op in ('row', 'matmul', 'take'):
            use(names.pop(0), {'row': 'row', 'matmul': 'matmul', 'take': 'table'}[op])
        for n in names + [y]:
            if n not in inline:
                use(n, 'vector')
    for n in [*m.state, *m.next.values(), *m.rand, m.output]:
        use(n, 'vector')

    def contents(n):
        """The words of a constant, as rows of elements."""
        c, how = m.const[n], layout[n]
        if how == 'table':
            return c.reshape(-1, 1)
        if how == 'vector':
            return np.pad(c, (0, words(len(c)) * V - len(c))).reshape(-1, V)
        rows, cols = c.shape
        if how == 'row':
            return np.pad(c, ((0, 0), (0, words(cols) * V - cols))).reshape(-1, V)
        c = np.pad(c, ((0, words(rows, L) * L - rows), (0, 0)))
        return c.reshape(-1, L, cols).transpose(0, 2, 1).reshape(-1, L)

    const = {n: contents(n) for n in layout if n in m.const}
    depth = {n: len(const[n]) if n in const else words(size[n]) for n in layout}
    width = {n: bits(*m.range[n]) for n in m.range}
    mats = [n for n in layout if layout[n] == 'matmul']
    M = max([width[n] for n in mats] + [1])  # every matrix for matmul is stored this wide
    width.update({n: M for n in mats})
    W = max(width[n] for n in layout)  # the widest value in memory
    A = max([width[y] for y, op, _ in m.code if op == 'matmul'] + [1])  # the widest sum
    X = index(m.range[m.input][1] + 1)
    K = index(max([depth[n] for n in layout if layout[n] in ('row', 'matmul')] + [1]))
    J2 = f'j2[{lv - 1}:0]' if lv else '0'  # the vector lane of column j2
    LV = max(lv, 1)  # the width of an index into a word of a vector

    def lane(n, p):
        """Element p of word d from memory n, or of the vector n the lane computes."""
        w = width[n]
        return f'v_{n}' if n in inline else f'$signed(d_{n}[{p}*{w} +: {w}])'

    # Each operation of the circuit: (comment, destination, rows, columns, columns
    # of the last row, what it reads, the result of vector lane p, the column of
    # the last product of a matrix, the ticks by which its results lag). It reads
    # its columns one tick each, then stores one word of results, or for a matrix
    # one word a tick from the column of its last product.
    ops = []

    def operation(comment, y, rows, cols, read='', result='0', last=None, end=None, late=0):
        ops.append((comment, y, rows, cols, last or cols, read, result, end, late))

    # The vectors each vector lane computes, each in a register some ticks behind
    # the reads from memory, and the registers that delay a vector to meet one
    # that is later.
    computed, late, delayed = [], {}, set()
    lookups = {}  # for each table, how each take reads it

    def at(n, k):
        """Vector n in vector lane p, k ticks behind the reads from memory."""
        if k == late.get(n, 0):
            return lane(n, 'p')
        if (n, k) not in delayed:
            delayed.add((n, k))
            computed.append(f'        reg signed [{width[n] - 1}:0] l{k}_{n}; always @(posedge clk) l{k}_{n} <= {at(n, k - 1)};')
        return f'l{k}_{n}'

    for h in m.state:
        operation(f'clear {h}', h, words(size[h]), 1)
    first = len(ops)
    for y, (n, b) in m.rand.items():  # lane p takes the draw gs holds for it
        operation(f'rand {y} {n} {b}', y, words(n), 1, f"tail = {LV}'d{n - (words(n) - 1) * V - 1}; ",
                  f'gs[p*32 + {32 - b} +: {b}]')
    draws = ' || '.join(f'op == {i}' for i in range(first, len(ops))) or '0'
    for y, op, (a, *rest) in m.code:
        comment, rows = ' '.join(map(str, (op, y, a, *rest))), words(size[y])
        if op == 'row':
            operation(comment, y, rows, 1, f"base = x[{X - 1}:0] * {K}'d{rows}; ", lane(a, 'p'))
        elif op == 'matmul':  # each row of matrix lanes sums its columns, then fills up to S words
            cols, groups = size[rest[0]], words(size[y], L)
            read = f'a = j >> {lv}; t = {lane(rest[0], J2)}; w = d_{a}; '
            operation(comment, y, groups, cols + S - 1, read, f'$signed(full[p*{A} +: {A}])',
                      cols + rows - (groups - 1) * S - 1, cols - 1, 1)
        elif op == 'take':  # each vector lane reads its own copy of the table
            b = rest[0]
            lookups.setdefault(a, []).append(f'{len(ops)}: q_{a} <= m_{a}[d_{b}[p*{width[b]} +: {min(width[b], index(size[a]))}]];')
            operation(comment, y, rows, 1, '', f'q_{a}', late=1)
        elif op == 'argmax':  # a word a tick, against best, the largest element so far, in ix
            n = size[a]
            read = f"a = j; tail = {LV}'d{n - (words(n) - 1) * V - 1}; " + ''.join(
                f'u[{p * W} +: {W}] = $signed(d_{a}[{p * width[a]} +: {width[a]}]); ' for p in range(V))
            operation(comment, y, 1, words(n), read, f'better ? at{2 * V - 2} : ix', late=1 + lv)  # and a tick a round
        else:  # on vectors as late as the latest it reads
            k = max(late.get(n, 0) for n in [a, *rest])
            if op == 'shr':
                result = f'{at(a, k)} >>> {rest[0]}'
            elif op == 'clamp':  # limits outside the bounds of a never apply
                w, e = width[a], at(a, k)
                lo, hi = (f"{w}'sh{v & (1 << w) - 1:x}"
                          for v in (max(rest[0], m.range[a][0]), min(rest[1], m.range[a][1])))
                result = f'{e} < {lo} ? {lo} : {e} > {hi} ? {hi} : {e}'
            else:
                result = f'{at(a, k)} {SIGN[op]} {at(rest[0], k)}'
            if y in inline:  # a register, a tick later
                late[y] = k + 1
                computed.append(f'        reg signed [{width[y] - 1}:0] v_{y}; always @(posedge clk) v_{y} <= {result};')
            else:
                operation(comment, y, rows, 1, '', result, late=k)
    emit = len(ops)
    operation(f'out {m.output}', None, 1, size[m.output], f'a = j >> {lv}; t = {lane(m.output, J2)}; ', late=1)
    for h, a in m.next.items():
        operation(f'next {h} {a}', h, words(size[h]), 1, '', lane(a, 'p'))
    N = index(max([o[2] for o in ops] + [o[3] for o in ops] + list(depth.values()) + [V + 1]))

    memories, reads, wires, packs, tables, cases, results = [], [], [], [], [], [], []
    for n, how in layout.items():
        w, address = width[n], {'vector': 'a', 'matmul': 'k', 'row': 'k'}.get(how)
        if how == 'table':  # a copy in each vector lane
            tables.append(f'        reg signed [{w - 1}:0] m_{n} [0:{depth[n] - 1}], q_{n};\n'
                          f'        initial $readmemh("{n}.hex", m_{n});\n'
                          f'        always @(posedge clk) case (op) {" ".join(lookups[n])} endcase')
            continue
        word = f'[{(L if how == "matmul" else V) * w - 1}:0]'
        memories.append(f'    reg {word} m_{n} [0:{depth[n] - 1}], q_{n}, d_{n};')
        if n in const:
            memories.append(f'    initial $readmemh("{n}.hex", m_{n});')
        reads.append(f'        q_{n} <= m_{n}[{address}[{index(depth[n]) - 1}:0]]; d_{n} <= q_{n};')
        writers = ' || '.join(f'op == {i}' for i, o in enumerate(ops) if o[1] == n)
        if writers:
            reads.append(f'        if (put[2 + deep] && ({writers})) m_{n}[o[{index(depth[n]) - 1}:0]] <= r_{n};')
            wires.append(f'    wire [{V * w - 1}:0] r_{n};')
            packs.append(f'        assign r_{n}[p*{w} +: {w}] = r[{w - 1}:0];')
    T = 2 + max(o[8] for o in ops)  # the stage of the latest result
    for i, (comment, _, rows, cols, last, read, result, end, lag) in enumerate(ops):
        jmax = f"{N}'d{cols - 1}" if last == cols else f"i == {N}'d{rows - 1} ? {N}'d{last - 1} : {N}'d{cols - 1}"
        read += ('' if end is None else f"jend = {N}'d{end}; ") + (f"deep = {N}'d{lag}; " if lag else '')
        cases.append(f"            {i}: begin imax = {N}'d{rows - 1}; jmax = {jmax}; {read}end  // {comment}")
        if result != '0':
            results.append(f'                {i}: r = {result};')
    # A weight of up to three bits multiplies by adding t3 shifted by each of its
    # bits, the top one negative, so that the matrix lanes need no multipliers.
    shifted = [f"(w3[p*{M} + {b}] ? t3{f' <<< {b}' if b else ''} : {A}'sd0)" for b in range(M)]
    product = (f'$signed(w3[p*{M} +: {M}]) * t3' if M > 3 else
               ' + '.join(shifted[:-1] or [f"{A}'sd0"]) + f' - {shifted[-1]}')
    # For argmax, a tournament between the lanes of u3, a round a tick, in which
    # the first of equal elements wins and lanes past the end of the last word
    # come last. Each entrant carries the index of its element, and whether it
    # is from the first word.
    IX, MIN, rounds = N + lv, f"{W}'sh{1 << W - 1:x}", []
    for p in range(V):
        value = f"v[2] || {p} <= tail3 ? $signed(u3[{p * W} +: {W}]) : {MIN}" if p else f'u3[{W - 1}:0]'
        rounds.append(f'    wire signed [{W - 1}:0] max{p} = {value};\n'
                      f'    wire [{IX - 1}:0] at{p} = j3 * {V} + {p};\n'
                      f'    wire first{p} = zero3;')
    entrants = list(range(V))
    while len(entrants) > 1:
        pairs, entrants = entrants, []
        for a, b in zip(pairs[::2], pairs[1::2]):
            n = len(rounds)
            rounds.append(f'    reg signed [{W - 1}:0] max{n}; reg [{IX - 1}:0] at{n}; reg first{n};\n'
                          f'    always @(posedge clk) {{max{n}, at{n}, first{n}}} <= '
                          f'max{b} > max{a} ? {{max{b}, at{b}, first{b}}} : {{max{a}, at{a}, first{a}}};')
            entrants.append(n)
    assert entrants == [2 * V - 2]  # the winner, as argmax expects
    nl = '\n'
    verilog = f'''\
// Generated by compile.py, with {L} matrix lanes and {V} vector lanes.
// Hold seed while rst is high. Then, for each step, hold x and raise start for
// one cycle while ready. The elements of the output arrive on y, in order,
// one in each cycle that valid is high.
module permacast (
    input clk, rst, start,
    input [31:0] seed, x,
    output ready, valid,
    output signed [31:0] y
);
    // A memory m for every constant and vector, its read register q, and d,
    // which holds what q held a tick before.
{nl.join(memories)}

    // op: the operation in progress. i, j: the row and column being read.
    // k: the position in a matrix. run: a column is being read. v[s]: what was
    // read s ticks ago is on its way: in q at stage 1, in d at stage 2, and in
    // t3, w3, u3 and tail3 at stage 3. put[s]: it is to be stored. j1, j2, j3:
    // its column, at stages 1 to 3. zero3: column 0 is at stage 3. keep3: the
    // sums kept in accs are being stored. o: the words stored so far. g: the
    // random generator, and gs its next values, one for each vector lane.
    reg [{index(len(ops)) - 1}:0] op;
    reg [{N - 1}:0] i, j, j1, j2, j3, o;
    reg [{K - 1}:0] k;
    reg [{T}:1] v, put;
    reg run, zero3, keep3;
    integer s;
    reg signed [{W - 1}:0] t3;
    reg [{L * M - 1}:0] w3;
    reg [{V * W - 1}:0] u3;
    reg [{LV - 1}:0] tail3;
    reg [31:0] g;
    function [31:0] xorshift(input [31:0] x);
        reg [31:0] z;
        begin z = x ^ (x << 13); z = z ^ (z >> 17); xorshift = z ^ (z << 5); end
    endfunction
    wire [31:0] {", ".join(f"g{n + 1} = xorshift(g{n or ''})" for n in range(V))};
    wire [{32 * V - 1}:0] gs = {{{", ".join(f"g{n}" for n in range(V, 0, -1))}}};

    // Each operation: its last row and column, the column jend of the last
    // product of a matrix, the ticks deep by which its results lag stage 2, the
    // word a it reads, the first word base of its matrix, the elements less one
    // in the last word, tail, and from d, t, an element it reads, w, the word of
    // its matrix for matmul, and u, the word for argmax.
    reg [{N - 1}:0] imax, jmax, jend, deep, a;
    reg [{K - 1}:0] base;
    reg [{LV - 1}:0] tail;
    reg signed [{W - 1}:0] t;
    reg [{L * M - 1}:0] w;
    reg [{V * W - 1}:0] u;
    always @* begin
        imax = 0; jmax = 0; jend = ~{N}'d0; deep = 0; a = i; base = 0; tail = 0; t = 0; w = 0; u = 0;
        case (op)
{nl.join(cases)}
        endcase
    end

    always @(posedge clk) begin
{nl.join(reads)}
    end

    // The matrix lanes. Each adds the product of its weight and t3 to its sum
    // in sums, which begins again at column 0. full holds the sums being
    // stored: those just made, then those kept in accs, which moves down a word
    // as each word is stored.
    reg [{L * A - 1}:0] accs;
    wire [{L * A - 1}:0] sums, full = keep3 ? accs : sums;
    genvar p;
    generate for (p = 0; p < {L}; p = p + 1) begin : mac
        assign sums[p*{A} +: {A}] = (zero3 ? {A}'sd0 : $signed(accs[p*{A} +: {A}])) + {product};
    end endgenerate
    always @(posedge clk) if (v[3]) accs <= put[3] ? full >> {V * A} : full;

    // For argmax: the largest element of each word, from the tournament, and
    // better: it is the largest so far, which is best, at ix.
{nl.join(rounds)}
    reg signed [{W - 1}:0] best;
    reg [{IX - 1}:0] ix;
    wire better = first{2 * V - 2} || max{2 * V - 2} > best;

    // Each vector lane: its result r, the vectors it computes where they are
    // read, with the registers that delay them, and its copy of each table.
{nl.join(wires)}
    generate for (p = 0; p < {V}; p = p + 1) begin : lane
        reg signed [{W - 1}:0] r;
{"".join(f"{c}{nl}" for c in computed + tables)}        always @* begin
            r = 0;
            case (op)
{nl.join(results)}
            endcase
        end
{nl.join(packs)}
    end endgenerate

    always @(posedge clk) begin
        v[1] <= run; put[1] <= run && (j == jmax || j >= jend);
        for (s = 2; s <= {T}; s = s + 1) begin  // only as far as the stage of the results of op
            v[s] <= s <= 2 + deep && v[s - 1]; put[s] <= s <= 2 + deep && put[s - 1];
        end
        j1 <= j; j2 <= j1; j3 <= j2; zero3 <= j2 == 0; keep3 <= j2 > jend;
        t3 <= t; w3 <= w; u3 <= u; tail3 <= tail;
        if (put[2 + deep]) o <= o + 1;
        if (better) begin best <= max{2 * V - 2}; ix <= at{2 * V - 2}; end
        if (v[2] && ({draws})) g <= gs[32 * (v[1] ? {V - 1} : tail) +: 32];  // as many draws as lanes took
        if (rst) begin
            op <= 0; run <= 0; v <= 0; put <= 0; g <= seed;
        end else if (run) begin  // read a column
            if (j <= jend) k <= k + 1;
            j <= j == jmax ? 0 : j + 1;
            if (j == jmax) begin i <= i + 1; run <= i != imax; end
        end else if (v[2 + deep] && !v[1 + deep])  // the last result is being stored
            op <= op == {len(ops) - 1} ? {first} : op + 1;
        else if (v == 0 && (op != {first} || start)) begin  // begin the operation
            i <= 0; j <= 0; k <= base; o <= 0; run <= 1;
        end
    end

    assign ready = op == {first} && !run && v == 0;
    assign valid = v[3] && op == {emit};
    assign y = t3;
endmodule
'''
    files = {'permacast.v': verilog}
    for n, c in const.items():
        w = width[n]
        files[f'{n}.hex'] = '\n'.join(f'{sum((v & (1 << w) - 1) << p * w for p, v in enumerate(row)):x}'
                                      for row in c.tolist()) + '\n'
    return files


if __name__ == '__main__':
    model, out = Model(open(sys.argv[1]).read()), Path(sys.argv[2])
    out.mkdir(exist_ok=True)
    for name, text in compile(model, *map(int, sys.argv[3:])).items():
        (out / name).write_text(text)
