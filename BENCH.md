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
| random-32 | f75ff9cdadc1 | 163,200 | 19,241 | 8.121 | 725,514 | 13,820 | 3,207,775 |
| stories-2 | 4a851456186c | 1,587,712 | 133,897 | 1.149 | 79,483 | 12,174 | 1,798,735 |
| loops2-units512 | c372d2317dc0 | 1,587,200 | 234,761 | 1.149 | 48,870 | 8,423 | 1,290,776 |
| levels3-units404 | 5acad3045405 | 1,588,544 | 114,093 | 1.097 | 95,825 | 11,125 | 2,028,130 |
| levels3-loops2-units404 | f78c1edc28e3 | 1,588,948 | 194,893 | 1.130 | 58,883 | 8,115 | 1,519,752 |
| levels7-units340 | 34ed38242a89 | 1,590,024 | 101,985 | 1.106 | 109,104 | 11,817 | 2,191,102 |
| levels3-units600-steps40k | 6f03816c5051 | 2,999,744 | 166,225 | 0.989 | 56,230 | 10,982 | 1,638,296 |
| levels3-units720-steps40k | 48079bf05481 | 4,091,264 | 196,345 | 0.952 | 44,258 | 10,717 | 1,343,384 |

## Chips

- **Ticks per step** are counted in simulation with Verilator 5.052.
- **Clock, logic cells, flip-flops, block RAMs and multipliers** are for a
  Lattice ECP5-85F, built with Yosys 0.66 and nextpnr 0.11.1 at seed 1.

| Model | Matrix lanes | Vector lanes | Ticks per step | Clock, MHz | Steps per second | Logic cells | Flip-flops | Block RAMs | Multipliers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random-32 | 1 | 1 | 16,056 | 101.9 | 6,344 | 1,841 | 698 | 16 | 1 |
| random-32 | 32 | 4 | 1,580 | 94.0 | 59,518 | 8,736 | 3,165 | 16 | 4 |
| random-32 | 256 | 4 | 1,363 | 75.2 | 55,139 | 39,434 | 7,709 | 14 | 4 |
| stories-2 | 1 | 1 | 723,576 | 64.3 | 89 | 1,975 | 773 | 102 | 1 |
| stories-2 | 32 | 4 | 24,320 | 79.7 | 3,276 | 8,707 | 3,139 | 109 | 4 |
| stories-2 | 256 | 4 | 4,671 | 72.4 | 15,505 | 42,064 | 9,628 | 131 | 4 |
| loops2-units512 | 1 | 1 | 1,248,395 | 71.6 | 57 | 2,222 | 1,025 | 105 | 2 |
| loops2-units512 | 32 | 4 | 41,075 | 77.3 | 1,881 | 10,055 | 4,124 | 114 | 8 |
| loops2-units512 | 256 | 4 | 7,118 | 71.8 | 10,082 | 43,300 | 10,613 | 136 | 8 |
| levels3-units404 | 1 | 1 | 484,032 | 68.5 | 141 | 2,015 | 799 | 102 | 1 |
| levels3-units404 | 32 | 4 | 17,042 | 83.9 | 4,925 | 11,516 | 3,433 | 123 | 4 |
| levels3-units404 | 256 | 4 | 3,969 | 63.1 | 15,892 | 59,547 | 11,488 | 180 | 4 |
| levels3-loops2-units404 | 1 | 1 | 810,887 | 62.3 | 77 | 2,325 | 1,056 | 105 | 2 |
| levels3-loops2-units404 | 32 | 4 | 27,842 | 83.8 | 3,011 | 12,220 | 4,442 | 128 | 8 |
| levels3-loops2-units404 | 256 | 4 | 5,903 | 65.6 | 11,118 | 56,806 | 12,497 | 185 | 8 |
| levels7-units340 | 1 | 1 | 364,096 | 66.8 | 183 | 2,151 | 819 | 102 | 2 |
| levels7-units340 | 32 | 4 | 13,162 | 61.2 | 4,646 | 8,222 | 3,753 | 126 | 36 |
| levels7-units340 | 256 | 4 | 3,553 | does not fit |  |  |  |  |  |
| levels3-units600-steps40k | 1 | 1 | 953,256 | 61.1 | 64 | 2,523 | 820 | 180 | 1 |
| levels3-units600-steps40k | 32 | 4 | 31,944 | 72.8 | 2,280 | 12,232 | 3,518 | 203 | 4 |
| levels3-units600-steps40k | 256 | 4 | 6,567 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 1 | 1 | 1,316,376 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 32 | 4 | 43,900 | does not fit |  |  |  |  |  |
| levels3-units720-steps40k | 256 | 4 | 7,587 | does not fit |  |  |  |  |  |
