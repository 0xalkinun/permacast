# Bench

What the compiler makes of each model, written by `python bench.py`. Every chip
and every CPU run here matches the reference exactly.

## Models

- **ROM and RAM bits** are the memory the model declares: its constants, and
  every other vector.
- **Bits per byte** are the cross-entropy of the next byte on
  stories-valid.txt, in its first 2,048 windows of 256 bytes, each begun from
  zero state. Lower is better.
- **CPU steps per second** are for `cpu.c` built with GCC 16.2.1, on one core
  of the 12th Gen Intel Core i7-12700KF, the best of three runs of 10,000
  steps.
- **GPU steps per second** are for `gpu.py` with PyTorch 2.11.0 on an NVIDIA
  GeForce RTX 3090: one stream, and 1,024 streams together.

| Model | SHA-256 | ROM, bits | RAM, bits | Bits per byte | CPU steps per second | GPU steps per second | GPU, 1,024 streams |
| --- | --- | --- | --- | --- | --- | --- | --- |
| random-32 | f75ff9cdadc1 | 163,200 | 19,241 | 8.121 | 731,980 | 13,730 | 3,213,195 |
| stories-2 | 4a851456186c | 1,587,712 | 133,897 | 1.149 | 80,482 | 11,623 | 1,800,465 |
| loops2-units512 | c372d2317dc0 | 1,587,200 | 234,761 | 1.149 | 49,745 | 8,622 | 1,289,843 |
| levels3-units404 | 5acad3045405 | 1,588,544 | 114,093 | 1.097 | 97,926 | 11,332 | 2,025,611 |
| levels3-loops2-units404 | f78c1edc28e3 | 1,588,948 | 194,893 | 1.130 | 58,762 | 8,402 | 1,519,756 |
| levels7-units340 | 34ed38242a89 | 1,590,024 | 101,985 | 1.106 | 108,432 | 11,776 | 2,191,756 |
| levels3-units600 | 3059d12d9ac6 | 2,999,744 | 165,625 | 1.012 | 56,299 | 11,227 | 1,637,646 |
| levels3-units720-steps40k | 48079bf05481 | 4,091,264 | 196,345 | 0.952 | 43,188 | 10,621 | 1,334,725 |

## Chips

- **Ticks per step** are counted in simulation with Verilator 5.052.
- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a
  Lattice ECP5-85F, built with Yosys 0.66 and nextpnr 0.11.1 at seed 1.

| Model | Lanes | Ticks per step | Clock, MHz | Steps per second | Logic cells | Flip-flops | Block RAMs | Multipliers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-32 | 1 | 16,041 | 76.5 | 4,767 | 1,599 | 543 | 16 | 2 |
| random-32 | 8 | 2,713 | 69.9 | 25,778 | 6,708 | 3,200 | 12 | 16 |
| random-32 | 32 | 1,285 | 56.1 | 43,619 | 14,429 | 14,722 | 11 | 64 |
| stories-2 | 1 | 727,401 | 66.7 | 92 | 1,506 | 588 | 102 | 2 |
| stories-2 | 8 | 91,633 | 60.2 | 657 | 9,145 | 3,654 | 110 | 16 |
| stories-2 | 32 | 23,515 | 57.8 | 2,458 | 23,058 | 15,324 | 90 | 64 |
| loops2-units512 | 1 | 1,256,306 | 60.5 | 48 | 1,789 | 776 | 105 | 3 |
| loops2-units512 | 8 | 157,754 | 62.1 | 394 | 10,824 | 5,109 | 120 | 24 |
| loops2-units512 | 32 | 40,052 | 52.9 | 1,322 | 30,117 | 22,469 | 90 | 96 |
| levels3-units404 | 1 | 486,993 | 61.7 | 127 | 1,688 | 606 | 102 | 2 |
| levels3-units404 | 8 | 62,055 | 60.3 | 972 | 9,785 | 3,810 | 113 | 16 |
| levels3-units404 | 32 | 16,357 | 51.4 | 3,145 | 24,887 | 16,032 | 104 | 64 |
| levels3-loops2-units404 | 1 | 817,070 | 61.6 | 75 | 2,014 | 797 | 105 | 3 |
| levels3-loops2-units404 | 8 | 103,731 | 57.6 | 555 | 12,524 | 5,307 | 123 | 24 |
| levels3-loops2-units404 | 32 | 26,987 | 50.7 | 1,878 | 32,973 | 23,361 | 104 | 96 |
| levels7-units340 | 1 | 366,545 | 60.1 | 164 | 1,906 | 617 | 102 | 2 |
| levels7-units340 | 8 | 46,935 | 57.5 | 1,225 | 12,288 | 4,327 | 103 | 16 |
| levels7-units340 | 32 | 12,545 | 49.5 | 3,944 | 25,638 | 16,408 | 105 | 64 |
| levels3-units600 | 1 | 957,785 | 53.4 | 56 | 2,332 | 626 | 179 | 2 |
| levels3-units600 | 8 | 120,431 | 54.7 | 454 | 10,088 | 3,726 | 194 | 16 |
| levels3-units600 | 32 | 31,049 | 48.1 | 1,549 | 33,275 | 16,376 | 180 | 64 |
| levels3-units720-steps40k | 1 | 1,321,865 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 8 | 165,941 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 32 | 42,881 | does not fit |  |  |  |  |  |
