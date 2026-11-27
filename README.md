# Permacast

Permacast is an open-source compiler that turns a trained language model into
a chip that is that model. The weights are built into the chip as read-only
memory, so there is no external memory and nothing to load. Each model is
trained to an exact integer specification, and the hardware must match the
software reference bit for bit.

Everything is open and built with open tools: the training code, the compiler,
the hardware source, the test results and, on open processes, the chip layout.
We publish every measurement against a tuned CPU and a GPU running the same
model, including the ones we lose.

## Roadmap

0. **Spec and reference.** A small model trained on text exports to the
   [model format](SPEC.md), and the reference reproduces the trainer's outputs
   exactly. *Done: a gated recurrent model of 720,896 ternary weights reaches
   1.13 bits per byte on held-out TinyStories.*
1. **Simulation.** The compiler emits Verilog whose simulated output is
   identical to the reference. *Done: the trained model matches on all 76,800
   numbers of a 300-step run, at 728,426 clock cycles per byte.*
2. **FPGA.** A low-cost board runs the model, and we publish speed and energy
   against a CPU and a GPU.
3. **Silicon.** Real chips on shared runs of the open 180nm process, holding a
   few million weights, with the layout published.
4. **Scale.** Larger models on newer processes, as funding allows. There the
   layout cannot be published, and we will say so.

## Files

- [SPEC.md](SPEC.md): the model format, the one interface between training
  and hardware.
- [ref.py](ref.py): the reference interpreter. It needs Python and NumPy.
- [test.py](test.py): tests for the reference and the compiler. Run
  `python test.py`. The compiler tests need Verilator.
- [train.py](train.py): trains a model on a text file, exports it, and checks
  that the reference reproduces the trainer's outputs. It needs PyTorch.
- [compile.py](compile.py): compiles a model to Verilog.
- [tb.v](tb.v): the testbench that runs a compiled model in a simulator.

## Training

The first model learns to continue children's stories, one byte at a time,
from the two text files of
[TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories)
(`TinyStoriesV2-GPT4-train.txt` and `TinyStoriesV2-GPT4-valid.txt`):

    python train.py train.txt valid.txt model.pc

## Simulation

Compile a model, simulate it with [Verilator](https://verilator.org) on the
bytes of any file, and compare with the reference:

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
