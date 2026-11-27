// The CPU baseline: a Permacast model run on one core.
//
// cc -O3 -march=native -fwrapv -o cpu cpu.c
// ./cpu model.pc [seed] < input    prints the output of each step, a line each
//
// It trusts ref.py to have checked the model. Every value fits in 32 bits, so
// arithmetic that wraps at 32 bits gives exact results. A matrix product is
// done in 8 or 16 bits when all its numbers fit, since narrower numbers do more
// work in each vector instruction. At the end it prints the steps per second
// to stderr.
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum { ROW, MATMUL, ADD, SUB, MUL, SHR, CLAMP, TAKE, ARGMAX, RAND, NOPS };
static const char *OPS[NOPS] = {"row", "matmul", "add", "sub", "mul", "shr", "clamp", "take", "argmax", "rand"};

typedef struct {      // n elements, in rows of cols
    char *name;
    int32_t *v;
    int16_t *halves;  // v in 16 bits, if it fits
    int8_t *bytes;    // v in 8 bits, if it fits
    int32_t *sums;    // the sum of each row, times 128
    int n, cols;
} Value;
typedef struct { int op, y, a, b; int32_t k, lo, hi; } Line;   // y = op(a, b) with numbers k, lo, hi

static Value values[4096];
static Line code[4096];
static int nvalues, ncode, nstates, states[4096], nexts[4096], input, output = -1;
static uint32_t rng;

static int find(const char *name) {
    for (int i = 0; i < nvalues; i++)
        if (!strcmp(values[i].name, name)) return i;
    fprintf(stderr, "unknown name: %s\n", name);
    exit(1);
}

static int create(const char *name, int n, int cols) {
    values[nvalues] = (Value){strdup(name), calloc(n, sizeof(int32_t)), NULL, NULL, NULL, n, cols};
    return nvalues++;
}

static void load(FILE *f) {
    char *line = NULL, *t[8];
    size_t size = 0;
    while (getline(&line, &size, f) > 0) {
        line[strcspn(line, "#")] = 0;
        int n = 0;
        for (char *s = strtok(line, " \t\n"); s && n < 8; s = strtok(NULL, " \t\n")) t[n++] = s;
        if (n == 0 || !strcmp(t[0], "permacast")) continue;
        if (!strcmp(t[0], "in")) input = create(t[1], 1, 1);
        else if (!strcmp(t[0], "state")) states[nstates++] = create(t[1], atoi(t[2]), 1);
        else if (!strcmp(t[0], "next")) {
            for (int i = 0; i < nstates; i++)
                if (states[i] == find(t[1])) nexts[i] = find(t[2]);
        } else if (!strcmp(t[0], "out")) output = find(t[1]);
        else if (!strcmp(t[0], "const")) {
            int rows = n == 4 ? atoi(t[2]) : 1, cols = atoi(t[n - 1]);
            Value *c = &values[create(t[1], rows * cols, cols)];
            for (int i = 0; i < c->n;) {
                if (getline(&line, &size, f) <= 0) exit(1);
                for (char *s = strtok(line, " \t\n"); s; s = strtok(NULL, " \t\n")) c->v[i++] = atoi(s);
            }
            c->halves = malloc(c->n * sizeof(int16_t));
            for (int i = 0; i < c->n && c->halves; i++)
                if (c->v[i] < INT16_MIN || c->v[i] > INT16_MAX) free(c->halves), c->halves = NULL;
                else c->halves[i] = c->v[i];
            c->bytes = calloc((unsigned)c->n, 1), c->sums = calloc(c->n / c->cols, sizeof(int32_t));
            for (int i = 0; i < c->n && c->bytes; i++)
                if (c->v[i] < INT8_MIN || c->v[i] > INT8_MAX) free(c->bytes), c->bytes = NULL;
                else c->bytes[i] = c->v[i], c->sums[i / c->cols] += 128 * c->v[i];
        } else {
            Line l = {0};
            while (l.op < NOPS && strcmp(OPS[l.op], t[0])) l.op++;
            if (l.op == NOPS) { fprintf(stderr, "unknown operation: %s\n", t[0]); exit(1); }
            if (l.op == RAND) l.k = atoi(t[3]);
            else {
                l.a = find(t[2]);
                if (l.op == SHR) l.k = atoi(t[3]);
                else if (l.op == CLAMP) l.lo = atoi(t[3]), l.hi = atoi(t[4]);
                else if (l.op != ARGMAX) l.b = find(t[3]);
            }
            Value *a = &values[l.a], *b = &values[l.b];
            int n = l.op == RAND ? atoi(t[2]) : l.op == ROW ? a->cols : l.op == MATMUL ? a->n / a->cols
                  : l.op == ARGMAX ? 1 : l.op == TAKE ? b->n : a->n;
            l.y = create(t[1], n, 1);
            code[ncode++] = l;
        }
    }
    free(line);
}

static int32_t dot(const int32_t *restrict w, const int32_t *restrict a, int n) {
    int32_t sum = 0;
    for (int j = 0; j < n; j++) sum += w[j] * a[j];
    return sum;
}

static int32_t dot_bytes(const int8_t *restrict w, const uint8_t *restrict a, int n) {
    int32_t sum = 0;
    for (int j = 0; j < n; j++) sum += w[j] * a[j];
    return sum;
}

static int32_t dot_halves(const int16_t *restrict w, const int16_t *restrict a, int n) {
    int32_t sum = 0;
    for (int j = 0; j < n; j++) sum += w[j] * a[j];
    return sum;
}

static void step(int32_t x) {
    values[input].v[0] = x;
    for (int i = 0; i < ncode; i++) {  // rand lines come first, in file order
        Line *l = &code[i];
        if (l->op != RAND) continue;
        Value *y = &values[l->y];
        for (int e = 0; e < y->n; e++) {
            rng ^= rng << 13, rng ^= rng >> 17, rng ^= rng << 5;
            y->v[e] = rng >> (32 - l->k);
        }
    }
    for (int i = 0; i < ncode; i++) {
        Line *l = &code[i];
        int32_t *y = values[l->y].v, *a = values[l->a].v, *b = values[l->b].v;
        int16_t *halves = values[l->a].halves;
        int8_t *bytes = values[l->a].bytes;
        int n = values[l->y].n, cols = values[l->a].cols;
        switch (l->op) {
        case ROW: memcpy(y, a + b[0] * cols, n * sizeof(int32_t)); break;
        case MATMUL: {  // in 8 bits if the numbers fit, with the vector moved up by 128, else 16 or 32
            int16_t half[cols];
            uint8_t byte[cols];
            for (int j = 0; j < cols; j++) {
                if (b[j] < INT8_MIN || b[j] > INT8_MAX) bytes = NULL;
                if (b[j] < INT16_MIN || b[j] > INT16_MAX) halves = NULL;
                half[j] = b[j], byte[j] = b[j] + 128;
            }
            int32_t *sums = values[l->a].sums;
            for (int r = 0; r < n; r++)
                y[r] = bytes ? dot_bytes(bytes + r * cols, byte, cols) - sums[r]
                     : halves ? dot_halves(halves + r * cols, half, cols) : dot(a + r * cols, b, cols);
            break;
        }
        case ADD: for (int e = 0; e < n; e++) y[e] = a[e] + b[e]; break;
        case SUB: for (int e = 0; e < n; e++) y[e] = a[e] - b[e]; break;
        case MUL: for (int e = 0; e < n; e++) y[e] = a[e] * b[e]; break;
        case SHR: for (int e = 0; e < n; e++) y[e] = a[e] >> l->k; break;
        case CLAMP:
            for (int e = 0; e < n; e++) y[e] = a[e] < l->lo ? l->lo : a[e] > l->hi ? l->hi : a[e];
            break;
        case TAKE: for (int e = 0; e < n; e++) y[e] = a[b[e]]; break;
        case ARGMAX:
            y[0] = 0;
            for (int e = 1; e < values[l->a].n; e++)
                if (a[e] > a[y[0]]) y[0] = e;
            break;
        }
    }
    for (int i = 0; i < nstates; i++)
        memcpy(values[states[i]].v, values[nexts[i]].v, values[states[i]].n * sizeof(int32_t));
}

int main(int argc, char **argv) {
    FILE *f = argc > 1 ? fopen(argv[1], "r") : NULL;
    if (!f) { fprintf(stderr, "usage: cpu model.pc [seed] < input\n"); return 1; }
    load(f);
    rng = argc > 2 ? strtoul(argv[2], NULL, 10) : 1;
    double seconds = 0;
    long steps = 0;
    for (int c; (c = getchar()) != EOF; steps++) {
        struct timespec t0, t1;
        clock_gettime(CLOCK_MONOTONIC, &t0);
        step(c);
        clock_gettime(CLOCK_MONOTONIC, &t1);
        seconds += t1.tv_sec - t0.tv_sec + (t1.tv_nsec - t0.tv_nsec) / 1e9;
        Value *y = &values[output];
        for (int e = 0; e < y->n; e++) printf(e ? " %d" : "%d", y->v[e]);
        putchar('\n');
    }
    fprintf(stderr, "%.0f steps per second\n", steps / seconds);
    return 0;
}
