// Testbench for a compiled model. It feeds the bytes of one file to the model
// and writes the output of each step to another, a line per step, in the same
// form as ref.py. Run it with +in=FILE +out=FILE.
module tb;
    reg clk = 0, rst = 1, start = 0, first = 1;
    reg [31:0] x;
    wire ready, valid;
    wire signed [31:0] y;
    reg [8191:0] path;
    integer in, out, c;

    permacast model (clk, rst, start, x, ready, valid, y);

    always #1 clk = ~clk;

    initial begin
        if (!$value$plusargs("in=%s", path)) $finish;
        in = $fopen(path, "rb");
        if (!$value$plusargs("out=%s", path)) $finish;
        out = $fopen(path, "w");
    end

    always @(posedge clk) begin
        rst <= 0;
        start <= 0;
        if (valid) begin
            if (!first) $fwrite(out, " ");
            $fwrite(out, "%0d", y);
            first <= 0;
        end
        if (ready && !start) begin
            if (!first) $fwrite(out, "\n");
            c = $fgetc(in);
            if (c < 0) $finish;
            x <= c;
            start <= 1;
            first <= 1;
        end
    end
endmodule
