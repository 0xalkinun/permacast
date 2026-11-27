# Permacast

Permacast is an open-source compiler that turns a trained language model into a
chip that is that model. The weights are built into the chip as read-only
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
   exactly. *In progress: the format and the reference exist, the trainer does
   not.*
1. **Simulation.** The compiler emits Verilog whose simulated output is
   identical to the reference.
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
- [test.py](test.py): tests for the reference. Run `python test.py`.

## Principles

- Everything stays as clean and minimal as possible: code, documents and
  layout.
- Few dependencies. We build what we can ourselves.
- Hardware matches the reference bit for bit, with no tolerance.
