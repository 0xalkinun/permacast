# Permacast model format, version 0

A model is a text file. It defines one function, `step`, which takes an input
integer and returns a vector of integers. The model keeps state between steps,
so its output depends on every input so far.

Every implementation, in software or hardware, must return exactly the same
integers for the same sequence of inputs. [ref.py](ref.py) is this document in
executable form, and all other implementations are tested against it.

## Values

Every value is a signed integer, and all arithmetic is exact. A value is the
input (a single integer), a vector, or a constant matrix.

Each value has bounds that hold on every step. They follow by interval
arithmetic from the range of the input, the declared ranges of the states and
the numbers in the constants. A model is valid only if the bounds of every
value lie within 32 bits, from −2³¹ to 2³¹ − 1. Hardware uses the bounds to
give each value only the bits it needs.

## File

The first line is `permacast 0`. Each line after it is an operation, written as
its name followed by its arguments, separated by spaces. Blank lines are
ignored, and so is everything from a `#` to the end of its line.

An integer is written in decimal, with a leading `-` if negative. Any other
token is a name. An operation that creates a value gives it a new name, and a
name can be used only on the lines after the one that creates it.

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
| `next h a` | After the step, state `h` takes the value of `a`. The bounds of `a` must lie within the range of `h`. |
| `out a` | The step returns the vector `a`. |

In `add`, `sub` and `mul`, `a` and `b` are vectors of the same size. A model
has exactly one `in`, one `out`, and one `next` for each state. Reading a
state gives its value from before the step, wherever the `next` line is.

The format puts no limit on the numbers in a constant, but hardware pays for
them: a matrix of only −1, 0 and 1 needs no multipliers.

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
