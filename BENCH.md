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
| random-32 | f75ff9cdadc1 | 163,200 | 19,241 | 8.121 | 722,060 | 13,701 | 3,208,005 |
| stories-2 | 4a851456186c | 1,587,712 | 133,897 | 1.149 | 79,877 | 11,595 | 1,800,771 |
| loops2-units512 | c372d2317dc0 | 1,587,200 | 234,761 | 1.149 | 48,717 | 8,418 | 1,291,712 |
| levels3-units404 | 5acad3045405 | 1,588,544 | 114,093 | 1.097 | 95,726 | 11,139 | 2,034,852 |
| levels3-loops2-units404 | f78c1edc28e3 | 1,588,948 | 194,893 | 1.130 | 58,727 | 8,104 | 1,521,471 |
| levels7-units340 | 34ed38242a89 | 1,590,024 | 101,985 | 1.106 | 109,458 | 11,420 | 2,194,573 |
| levels3-units600-steps40k | 6f03816c5051 | 2,999,744 | 166,225 | 0.989 | 56,499 | 10,859 | 1,638,570 |
| levels3-units720-steps40k | 48079bf05481 | 4,091,264 | 196,345 | 0.952 | 44,314 | 11,187 | 1,335,467 |

## Chips

- **Ticks per step** are counted in simulation with Verilator 5.052.
- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a
  Lattice ECP5-85F, built with Yosys 0.66 and nextpnr 0.11.1 at seed 1.

| Model | Matrix lanes | Vector lanes | Ticks per step | Clock, MHz | Steps per second | Logic cells | Flip-flops | Block RAMs | Multipliers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-32 | 1 | 1 | 15,545 | 90.5 | 5,821 | 1,743 | 691 | 16 | 1 |
| random-32 | 32 | 4 | 879 | 87.0 | 98,978 | 7,039 | 3,227 | 19 | 4 |
| random-32 | 256 | 4 | 662 | 76.5 | 115,487 | 28,765 | 7,771 | 17 | 4 |
| stories-2 | 1 | 1 | 723,065 | 66.8 | 92 | 1,760 | 769 | 102 | 1 |
| stories-2 | 32 | 4 | 23,619 | 79.0 | 3,343 | 7,176 | 3,213 | 112 | 4 |
| stories-2 | 256 | 4 | 3,970 | 76.2 | 19,184 | 31,826 | 9,698 | 134 | 4 |
| loops2-units512 | 1 | 1 | 1,247,884 | 62.8 | 50 | 2,086 | 1,021 | 105 | 2 |
| loops2-units512 | 32 | 4 | 40,374 | 87.0 | 2,156 | 8,100 | 4,198 | 117 | 8 |
| loops2-units512 | 256 | 4 | 6,417 | 76.8 | 11,969 | 32,738 | 10,683 | 139 | 8 |
| levels3-units404 | 1 | 1 | 483,521 | 72.3 | 150 | 1,890 | 796 | 102 | 1 |
| levels3-units404 | 32 | 4 | 16,341 | 79.6 | 4,870 | 9,644 | 3,509 | 126 | 4 |
| levels3-units404 | 256 | 4 | 3,268 | 63.1 | 19,309 | 48,394 | 11,560 | 183 | 4 |
| levels3-loops2-units404 | 1 | 1 | 810,376 | 64.0 | 79 | 2,151 | 1,053 | 105 | 2 |
| levels3-loops2-units404 | 32 | 4 | 27,141 | 76.5 | 2,818 | 10,351 | 4,518 | 131 | 8 |
| levels3-loops2-units404 | 256 | 4 | 5,202 | 67.1 | 12,893 | 49,061 | 12,569 | 188 | 8 |
| levels7-units340 | 1 | 1 | 363,585 | 65.0 | 179 | 1,997 | 813 | 102 | 2 |
| levels7-units340 | 32 | 4 | 12,461 | 57.8 | 4,638 | 7,913 | 3,827 | 129 | 36 |
| levels7-units340 | 256 | 4 | 2,852 | does not fit |  |  |  |  |  |
| levels3-units600-steps40k | 1 | 1 | 952,745 | 56.6 | 59 | 2,430 | 818 | 180 | 1 |
| levels3-units600-steps40k | 32 | 4 | 31,243 | 74.9 | 2,396 | 10,636 | 3,600 | 206 | 4 |
| levels3-units600-steps40k | 256 | 4 | 5,866 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 1 | 1 | 1,315,865 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 32 | 4 | 43,199 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 256 | 4 | 6,886 | does not fit |  |  |  |  |  |
