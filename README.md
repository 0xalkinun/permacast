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
| [cpu.c](cpu.c) | The CPU baseline: runs a model fast on one core |
| [stories.py](stories.py) | Fetches and prepares the text for the stories model |
| [train.py](train.py) | Trains a model on a text file and exports it |
| [compile.py](compile.py) | Compiles a model to Verilog |
| [tb.v](tb.v) | The testbench that runs a compiled model in a simulator |
| [chip.v](chip.v) | The chip: a compiled model behind a serial port |
| [chip_tb.v](chip_tb.v) | The testbench that talks to the chip through its serial port |
| [test.py](test.py) | Tests everything against the reference |
| [bench.py](bench.py) | Measures the chips against the CPU, into [BENCH.md](BENCH.md) |

The reference needs Python and NumPy, training needs PyTorch, the CPU
baseline and the tests need a C compiler, and simulation needs
[Verilator](https://verilator.org). The bench also needs
[Yosys](https://yosyshq.net/yosys) and
[nextpnr](https://github.com/YosysHQ/nextpnr) for the ECP5.

## Test

    python test.py

## Train

The first model learns to continue children's stories, one byte at a time.
Fetch and prepare the text of
[TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories), then
train on it:

    python stories.py
    python train.py data/stories-train.txt data/stories-valid.txt model.pc

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

To simulate the whole chip writing 300 bytes on its own, in the same folder:

    verilator --binary -Wno-WIDTHEXPAND --top chip_tb ../chip_tb.v ../chip.v \
        permacast.v --Mdir obj_chip -o sim
    ./obj_chip/sim +seed=1 +loop=300 +out=story

[chip.v](chip.v) describes the serial protocol.

## Bench

    python bench.py model.pc

This checks the compiled circuit against the reference, counts its clock ticks
per step, and builds it for a Lattice ECP5 to get its size and fastest clock.
It also times the CPU baseline on the same model.

## Principles

- Everything stays as clean and minimal as possible: code, documents and
  layout.
- Few dependencies. We build what we can ourselves.
- Hardware matches the reference bit for bit, with no tolerance.
