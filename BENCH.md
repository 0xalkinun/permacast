# Bench

What the compiler makes of each model, written by `python bench.py`. Every
circuit here matches the reference exactly.

- **Ticks per step** are counted in simulation with Verilator 5.052.
- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a
  Lattice ECP5-85F, built with Yosys 0.66 and nextpnr 0.11.1 at seed 1.
- **ROM and RAM bits** are the memory the circuit declares, on any target.

| Model | SHA-256 | Ticks per step | Clock, MHz | Steps per second | Logic cells | Flip-flops | Block RAMs | Multipliers | ROM, bits | RAM, bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-32 | f75ff9cdadc1 | 16,180 | 44.7 | 2,761 | 2,616 | 381 | 16 | 2 | 163,200 | 19,241 |
| stories-1 | 891025166d4a | 729,460 | 33.6 | 46 | 1,997 | 248 | 114 | 2 | 1,587,200 | 133,897 |
