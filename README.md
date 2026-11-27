# Permacast

Permacast is an open-source compiler that turns a trained model into a chip
that is that model. The weights are built into the chip as read-only memory,
so there is no external memory and nothing to load. Each model is trained to
an exact integer specification, and the hardware must match the software
reference bit for bit.

Everything we make is open: the training code, the compiler, the hardware
source, the test results and, on open processes, the chip layout. We publish
every measurement against a tuned CPU and a GPU running the same model,
including the ones we lose.

## The pieces

Everything meets at the model format: a text file of integer constants and a
short program of integer operations.

| File | What it does |
|---|---|
| [SPEC.md](SPEC.md) | Defines the model format |
| [ref.py](ref.py) | The reference: runs a model and defines what is correct |
| [train.py](train.py) | Trains a model on a text file and exports it |
| [compile.py](compile.py) | Compiles a model to Verilog |
| [tb.v](tb.v) | The testbench that runs a compiled model in a simulator |
| [test.py](test.py) | Tests the reference and the compiler |

The reference needs Python and NumPy, training needs PyTorch, and simulation
needs [Verilator](https://verilator.org).

## Test

    python test.py

## Train

The first model learns to continue children's stories, one byte at a time,
from the two text files of
[TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories)
(`TinyStoriesV2-GPT4-train.txt` and `TinyStoriesV2-GPT4-valid.txt`):

    python train.py train.txt valid.txt model.pc

The exported model reads a byte and answers with its choice of the next one.
Training ends by checking that the reference reproduces the trainer's scores
exactly.

## Simulate

Compile a model, simulate it on the bytes of any file, and compare with the
reference:

    python compile.py model.pc out
    cd out
    verilator --binary -Wno-WIDTHEXPAND --top tb ../tb.v permacast.v \
        --Mdir obj -o sim
    ./obj/sim +in=input +out=output
    python ../ref.py ../model.pc < input | cmp - output

## Principles

- Everything stays as clean and minimal as possible: code, documents and
  layout.
- Few dependencies. We build what we can ourselves.
- Hardware matches the reference bit for bit, with no tolerance.
