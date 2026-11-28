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
| random-32 | f75ff9cdadc1 | 163,200 | 19,241 | 8.121 | 724,672 | 14,083 | 3,207,338 |
| stories-2 | 4a851456186c | 1,587,712 | 133,897 | 1.149 | 81,232 | 11,635 | 1,800,187 |
| loops2-units512 | c372d2317dc0 | 1,587,200 | 234,761 | 1.149 | 48,819 | 8,535 | 1,289,498 |
| levels3-units404 | 5acad3045405 | 1,588,544 | 114,093 | 1.097 | 95,453 | 11,109 | 2,030,662 |
| levels3-loops2-units404 | f78c1edc28e3 | 1,588,948 | 194,893 | 1.130 | 59,036 | 7,938 | 1,520,461 |
| levels7-units340 | 34ed38242a89 | 1,590,024 | 101,985 | 1.106 | 109,701 | 11,417 | 2,193,369 |
| levels3-units600-steps40k | 6f03816c5051 | 2,999,744 | 166,225 | 0.989 | 56,547 | 11,406 | 1,638,167 |
| levels3-units720-steps40k | 48079bf05481 | 4,091,264 | 196,345 | 0.952 | 43,324 | 10,860 | 1,334,357 |

## Chips

- **Ticks per step** are counted in simulation with Verilator 5.052.
- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a
  Lattice ECP5-85F, built with Yosys 0.66 and nextpnr 0.11.1 at seed 1.

| Model | Matrix lanes | Vector lanes | Ticks per step | Clock, MHz | Steps per second | Logic cells | Flip-flops | Block RAMs | Multipliers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-32 | 1 | 1 | 16,041 | 97.0 | 6,045 | 1,918 | 551 | 16 | 1 |
| random-32 | 32 | 4 | 1,565 | 81.1 | 51,852 | 7,844 | 2,399 | 16 | 4 |
| random-32 | 256 | 4 | 1,348 | 66.8 | 49,548 | 37,038 | 6,495 | 14 | 4 |
| stories-2 | 1 | 1 | 727,401 | 65.3 | 90 | 1,711 | 599 | 102 | 1 |
| stories-2 | 32 | 4 | 25,265 | 78.1 | 3,090 | 8,230 | 2,265 | 109 | 4 |
| stories-2 | 256 | 4 | 5,616 | 63.0 | 11,209 | 42,961 | 6,514 | 131 | 4 |
| loops2-units512 | 1 | 1 | 1,256,306 | 59.6 | 47 | 2,046 | 787 | 105 | 2 |
| loops2-units512 | 32 | 4 | 43,034 | 78.3 | 1,819 | 9,260 | 2,995 | 114 | 8 |
| loops2-units512 | 256 | 4 | 9,077 | 67.5 | 7,437 | 43,732 | 7,244 | 136 | 8 |
| levels3-units404 | 1 | 1 | 486,993 | 63.4 | 130 | 1,939 | 618 | 102 | 1 |
| levels3-units404 | 32 | 4 | 17,771 | 69.9 | 3,933 | 18,975 | 2,392 | 123 | 4 |
| levels3-units404 | 256 | 4 | 4,698 | 57.1 | 12,154 | 70,698 | 7,087 | 180 | 4 |
| levels3-loops2-units404 | 1 | 1 | 817,070 | 62.1 | 76 | 2,275 | 809 | 105 | 2 |
| levels3-loops2-units404 | 32 | 4 | 29,369 | 68.2 | 2,322 | 12,094 | 3,136 | 128 | 8 |
| levels3-loops2-units404 | 256 | 4 | 7,430 | 54.3 | 7,311 | 72,577 | 7,831 | 185 | 8 |
| levels7-units340 | 1 | 1 | 366,545 | 63.7 | 174 | 2,100 | 630 | 102 | 2 |
| levels7-units340 | 32 | 4 | 13,763 | 53.0 | 3,851 | 15,054 | 2,544 | 126 | 36 |
| levels7-units340 | 256 | 4 | 4,154 | does not fit |  |  |  |  |  |
| levels3-units600-steps40k | 1 | 1 | 957,785 | 53.9 | 56 | 2,776 | 638 | 180 | 1 |
| levels3-units600-steps40k | 32 | 4 | 33,065 | 62.2 | 1,881 | 19,434 | 2,473 | 203 | 4 |
| levels3-units600-steps40k | 256 | 4 | 7,688 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 1 | 1 | 1,321,865 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 32 | 4 | 45,261 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 256 | 4 | 8,948 | does not fit |  |  |  |  |  |
