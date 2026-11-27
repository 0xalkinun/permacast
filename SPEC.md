# Permacast model format, version 0

A model is a text file. It defines one function, `step`, which takes an input
integer and returns a vector of integers. The model keeps state between steps,
so its output depends on every input so far. It can also draw random numbers,
which depend only on a seed chosen before the first step.

Every implementation, in software or hardware, must return exactly the same
integers for the same seed and sequence of inputs. [ref.py](ref.py) is this
document in executable form, and all other implementations are tested against
it.

## Values

Every value is a signed integer, and all arithmetic is exact. A value is the
input (a single integer), a vector, or a constant matrix.

Each value has bounds that hold on every step. They follow by interval
arithmetic from the range of the input, the declared ranges of the states,
the sizes of the random numbers and the numbers in the constants. A model is
valid only if the bounds of every value lie within 32 bits, from −2³¹ to
2³¹ − 1. Hardware uses the bounds to give each value only the bits it needs.

## File

The first line is `permacast 0`. Each line after it is an operation, written
as its name followed by its arguments, separated by spaces. Blank lines are
ignored, and so is everything from a `#` to the end of its line.

An integer is written in decimal, with a leading `-` if negative. A name is a
letter or underscore followed by letters, digits and underscores. An operation
that creates a value gives it a new name, and a name can be used only on the
lines after the one that creates it.

## Operations

| Line | Meaning |
|---|---|
| `in x n` | `x` is the input of the step, with 0 ≤ `x` < `n`. |
| `state h n lo hi` | `h` is a vector of `n` integers kept between steps. It is zero before the first step and always within `lo` to `hi`, which must include zero. |
| `const c n` | `c` is a constant vector. The next line holds its `n` integers. |
| `const c r k` | `c` is a constant matrix. The next `r` lines hold `k` integers each. |
| `row y m x` | `y` is row `x` of the constant matrix `m`, which needs a row for every input. |
| `matmul y m a` | `y` is the constant matrix `m` times the vector `a`. |
| `add y a b` | `y[i] = a[i] + b[i]` |
| `sub y a b` | `y[i] = a[i] - b[i]` |
| `mul y a b` | `y[i] = a[i] * b[i]` |
| `shr y a k` | `y[i] = floor(a[i] / 2^k)`, with `k` ≥ 0. |
| `clamp y a lo hi` | `y[i]` is `a[i]` limited to the range `lo` to `hi`. |
| `take y t a` | `y[i] = t[a[i]]`, where `t` is a constant vector. The bounds of `a` must lie within its indices. |
| `argmax y a` | `y` has one element: the index of the largest element of `a`, and the smallest such index if several are equal. |
| `rand y n b` | `y` is a vector of `n` random integers of `b` bits each, from 0 to 2^b − 1. |
| `next h a` | After the step, state `h` takes the value of `a`. The bounds of `a` must lie within the range of `h`. |
| `out a` | The step returns the vector `a`. |

In `add`, `sub` and `mul`, `a` and `b` are vectors of the same size. A model
has exactly one `in`, one `out`, and one `next` for each state. Reading a
state gives its value from before the step, wherever the `next` line is.

The format puts no limit on the numbers in a constant, but hardware pays for
them: a matrix of only −1, 0 and 1 needs no multipliers.

## Random numbers

A model has one random generator, a 32-bit number `s`. Before the first step
`s` is the seed, which is from 0 to 2³² − 1. At the start of each step the
`rand` lines are filled in file order, one element after another. Each
element first changes `s` in three stages, keeping its low 32 bits, and then
takes the top `b` bits of `s`:

    s = s xor (s << 13)
    s = s xor (s >> 17)
    s = s xor (s << 5)

A seed of zero stays zero, so every random number is zero and the model
always does the same thing.

With `rand`, `take` and `argmax` a model can choose its own output. Adding a
table of random noise to a vector of scores and taking the `argmax` picks an
index at random, with the likeliest picked most often.

## Example

```
permacast 0
in x 2
state h 2 -4 4
const E 2 2
5 -3
-6 4
const W 2 2
1 -1
0 1
const g 2
3 1
row e E x       # look up the input
matmul r W h    # mix in the state
add a e r
mul m a g
shr s m 1
clamp c s -4 4
sub d c h       # the output is the change in state
next h c
out d
```

For the inputs 0, 1, 1 the steps return `4 -2`, then `-4 3`, then `-4 1`.
