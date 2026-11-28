"""Compile a Permacast model to Verilog.

python compile.py model.pc out [matrix lanes [vector lanes]]    writes to out

The circuit keeps every constant in a read-only memory and every vector in a
memory of its own, each as wide as the bounds of its values require. It runs
the operations of the model in order. A vector that only elementwise
operations make and read has no memory or operation of its own: each vector
lane computes it in registers, one operation a tick, while the operation that
reads it reads the same word.

Its lanes work side by side, in two kinds, each a power of two. Matrix lanes
only multiply and add: each sums a row of a matrix product, a weight a tick,
then hands its sum to the vector lanes, which do everything else and are no
more in number. A word of a vector holds an element for each vector lane, and
most operations take a tick per word. Those whose elements follow one
another, such as drawing random numbers, take a tick per element.
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
    J1 = f'j1[{lv - 1}:0]' if lv else '0'  # the vector lane of column j1
    JP = 'jp' if lv else '0'              # the vector lane before that of column j

    def lane(n, p, word='d'):
        """Element p of word d from memory n, or of q, or of the vector n the lane computes."""
        if n in inline:
            return f'v_{n}'
        w = width[n]
        return f'{word}_{n}' if layout[n] == 'table' else f'$signed({word}_{n}[{p}*{w} +: {w}])'

    # Each operation of the circuit: (comment, destination, rows, columns, columns
    # of the last row, what it reads, the result of vector lane p, the column of
    # the last product of a matrix). It reads its columns one tick each, then
    # stores one word of results, or for a matrix one word a tick from the column
    # of its last product.
    ops, computed, ticks = [], [], {}  # the vectors each lane computes, and the ticks each takes

    def operation(comment, y, rows, cols, read='', result='0', last=None, end=None):
        ops.append((comment, y, rows, cols, last or cols, read, result, end))

    for h in m.state:
        operation(f'clear {h}', h, words(size[h]), 1)
    first = len(ops)
    for y, (n, b) in m.rand.items():
        operation(f'rand {y} {n} {b}', y, words(n), V, '', f'j2 == p ? gn[31:{32 - b}] : acc', n - (words(n) - 1) * V)
    draws = ' || '.join(f'op == {i}' for i in range(first, len(ops))) or '0'
    for y, op, (a, *rest) in m.code:
        comment, rows = ' '.join(map(str, (op, y, a, *rest))), words(size[y])
        if op == 'row':
            operation(comment, y, rows, 1, f"base = x[{X - 1}:0] * {K}'d{rows}; ", lane(a, 'p'))
        elif op == 'matmul':  # each row of matrix lanes sums its columns, then fills up to S words
            cols, groups = size[rest[0]], words(size[y], L)
            read = f'a = j >> {lv}; t = {lane(rest[0], J1, "q")}; w = q_{a}; '
            operation(comment, y, groups, cols + S - 1, read, f'$signed(full[p*{A} +: {A}])',
                      cols + rows - (groups - 1) * S - 1, cols - 1)
        elif op == 'take':  # in each row, read the word of indices, then the table once per lane
            b, n = rest[0], size[y]
            read = f'ta = q_{b}[{JP}*{width[b]} +: {min(width[b], index(size[a]))}]; '
            operation(comment, y, rows, V + 1, read, f'j2 == p + 1 ? {lane(a, "p")} : acc', n - (rows - 1) * V + 1)
        elif op == 'argmax':  # acc holds the index of the largest element so far
            read, result = f'a = j >> {lv}; t = {lane(a, J1, "q")}; ', f'j2 == 0 || t2 > best ? j2[{index(size[a]) - 1}:0] : acc'
            operation(comment, y, 1, size[a], read, result)
        else:
            if op == 'shr':
                result = f'{lane(a, "p")} >>> {rest[0]}'
            elif op == 'clamp':  # limits outside the bounds of a never apply
                w = width[a]
                lo, hi = (f"{w}'sh{v & (1 << w) - 1:x}"
                          for v in (max(rest[0], m.range[a][0]), min(rest[1], m.range[a][1])))
                result = f'{lane(a, "p")} < {lo} ? {lo} : {lane(a, "p")} > {hi} ? {hi} : {lane(a, "p")}'
            else:
                result = f'{lane(a, "p")} {SIGN[op]} {lane(rest[0], "p")}'
            wait = max(ticks.get(n, 0) for n in [a, *rest])  # for the vectors it reads to settle
            if y in inline:  # a register, a tick behind what it reads
                ticks[y] = wait + 1
                computed.append(f'        reg signed [{width[y] - 1}:0] v_{y}; always @(posedge clk) v_{y} <= {result};')
            else:  # it reads the same word until then
                operation(comment, y, rows, wait + 1, '', result)
    emit = len(ops)
    operation(f'out {m.output}', None, 1, size[m.output], f'a = j >> {lv}; t = {lane(m.output, J1, "q")}; ')
    for h, a in m.next.items():
        operation(f'next {h} {a}', h, words(size[h]), 1, '', lane(a, 'p'))
    N = index(max([o[2] for o in ops] + [o[3] for o in ops] + list(depth.values()) + [V + 1]))

    memories, reads, wires, packs, cases, results = [], [], [], [], [], []
    for n, how in layout.items():
        w, at = width[n], {'table': 'ta', 'vector': 'a', 'matmul': 'k', 'row': 'k'}[how]
        word = f'signed [{w - 1}:0]' if how == 'table' else f'[{(L if how == "matmul" else V) * w - 1}:0]'
        memories.append(f'    reg {word} m_{n} [0:{depth[n] - 1}], q_{n}, d_{n};')
        if n in const:
            memories.append(f'    initial $readmemh("{n}.hex", m_{n});')
        reads.append(f'        q_{n} <= m_{n}[{at}[{index(depth[n]) - 1}:0]]; d_{n} <= q_{n};')
        writers = ' || '.join(f'op == {i}' for i, o in enumerate(ops) if o[1] == n)
        if writers:
            reads.append(f'        if (store2 && ({writers})) m_{n}[o[{index(depth[n]) - 1}:0]] <= r_{n};')
            wires.append(f'    wire [{V * w - 1}:0] r_{n};')
            packs.append(f'        assign r_{n}[p*{w} +: {w}] = r[{w - 1}:0];')
    for i, (comment, _, rows, cols, last, read, result, end) in enumerate(ops):
        jmax = f"{N}'d{cols - 1}" if last == cols else f"i == {N}'d{rows - 1} ? {N}'d{last - 1} : {N}'d{cols - 1}"
        read += '' if end is None else f"jend = {N}'d{end}; "
        cases.append(f"            {i}: begin imax = {N}'d{rows - 1}; jmax = {jmax}; {read}end  // {comment}")
        if result != '0':
            results.append(f'                {i}: r = {result};')
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
    // k: the position in a matrix. run: a column is being read. v1: q holds
    // what was read, for column j1. last1: it is the last column. store1: a
    // word is stored then. v2, j2, last2, store2: the same a tick later, for d,
    // t2 and w2. o: the words stored so far. best: the largest element so far.
    // g: the random generator, gn its next value.
    reg [{index(len(ops)) - 1}:0] op;
    reg [{N - 1}:0] i, j, j1, j2, o;
    reg [{K - 1}:0] k;
    reg run, v1, last1, store1, v2, last2, store2;
    reg signed [{W - 1}:0] best, t2;
    reg [{L * M - 1}:0] w2;
    reg [31:0] g;
    wire [31:0] g1 = g ^ (g << 13), g2 = g1 ^ (g1 >> 17), gn = g2 ^ (g2 << 5);
{f"    wire [{lv - 1}:0] jp = j[{lv - 1}:0] - 1'b1;{nl}" if lv else ""}
    // Each operation: its last row and column, the column jend of the last
    // product of a matrix, the word a and table entry ta it reads, the first
    // word base of its matrix, t, an element it reads, and w, the word of its
    // matrix for matmul.
    reg [{N - 1}:0] imax, jmax, jend, a, ta;
    reg [{K - 1}:0] base;
    reg signed [{W - 1}:0] t;
    reg [{L * M - 1}:0] w;
    always @* begin
        imax = 0; jmax = 0; jend = ~{N}'d0; a = i; ta = 0; base = 0; t = 0; w = 0;
        case (op)
{nl.join(cases)}
        endcase
    end

    always @(posedge clk) begin
{nl.join(reads)}
    end

    // The matrix lanes. Each adds the product of its weight and t2 to its sum
    // in sums, which begins again at column 0. full holds the sums being
    // stored: those just made, then those kept in accs, which moves down a word
    // as each word is stored.
    reg [{L * A - 1}:0] accs;
    wire [{L * A - 1}:0] sums, full = j2 <= jend ? sums : accs;
    genvar p;
    generate for (p = 0; p < {L}; p = p + 1) begin : mac
        assign sums[p*{A} +: {A}] = (j2 == 0 ? {A}'sd0 : $signed(accs[p*{A} +: {A}])) + $signed(w2[p*{M} +: {M}]) * t2;
    end endgenerate
    always @(posedge clk) if (v2) accs <= store2 ? full >> {V * A} : full;

    // Each vector lane: its result r, acc, its result so far in the row, and
    // the vectors it computes where they are read.
{nl.join(wires)}
    generate for (p = 0; p < {V}; p = p + 1) begin : lane
        reg signed [{W - 1}:0] acc, r;
{f"{nl.join(computed)}{nl}" if computed else ""}        always @* begin
            r = 0;
            case (op)
{nl.join(results)}
            endcase
        end
        always @(posedge clk) acc <= v2 && !last2 ? r : 0;
{nl.join(packs)}
    end endgenerate

    always @(posedge clk) begin
        v1 <= run; last1 <= run && j == jmax; store1 <= run && (j == jmax || j >= jend); j1 <= j;
        v2 <= v1; last2 <= last1; store2 <= store1; j2 <= j1; t2 <= t; w2 <= w;
        if (store2) o <= o + 1;
        best <= j2 == 0 || t2 > best ? t2 : best;
        if (v2 && ({draws})) g <= gn;
        if (rst) begin
            op <= 0; run <= 0; v1 <= 0; last1 <= 0; store1 <= 0; v2 <= 0; last2 <= 0; store2 <= 0; g <= seed;
        end else if (run) begin  // read a column
            if (j <= jend) k <= k + 1;
            j <= j == jmax ? 0 : j + 1;
            if (j == jmax) begin i <= i + 1; run <= i != imax; end
        end else if (v2 && !v1)  // the last result is being stored
            op <= op == {len(ops) - 1} ? {first} : op + 1;
        else if (!v1 && (op != {first} || start)) begin  // begin the operation
            i <= 0; j <= 0; k <= base; o <= 0; run <= 1;
        end
    end

    assign ready = op == {first} && !run && !v1 && !v2;
    assign valid = v2 && op == {emit};
    assign y = t2;
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
