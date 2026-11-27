// Testbench for a compiled model. It feeds the bytes of one file to the model
// and writes the output of each step to another, a line per step, in the same
// form as ref.py. Run it with +in=FILE +out=FILE, and +seed=NUMBER to set a
// seed other than 1. At the end it prints the clock ticks of one step.
module tb;
    reg clk = 0, rst = 1, start = 0, first = 1;
    reg [31:0] seed, x;
    wire ready, valid;
    wire signed [31:0] y;
    reg [8191:0] path;
    integer in, out, c, now = 0, began = 0;

    permacast model (clk, rst, start, seed, x, ready, valid, y);

    always #1 clk = ~clk;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("in=%s", path)) $finish;
        in = $fopen(path, "rb");
        if (!$value$plusargs("out=%s", path)) $finish;
        out = $fopen(path, "w");
    end

    always @(posedge clk) begin
        rst <= 0;
        start <= 0;
        now <= now + 1;
        if (valid) begin
            if (!first) $fwrite(out, " ");
            $fwrite(out, "%0d", y);
            first <= 0;
        end
        if (ready && !start) begin
            if (!first) $fwrite(out, "\n");
            c = $fgetc(in);
            if (c < 0) begin
                $display("%0d", now - began);
                $finish;
            end
            x <= c;
            start <= 1;
            first <= 1;
            began <= now;
        end
    end
endmodule
