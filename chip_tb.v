// Testbench for the chip. It talks to the chip through its serial port, as a
// host would, and writes every byte the chip sends to a file as a number on a
// line of its own. Run it with +seed=NUMBER +out=FILE and one of:
//
// +in=FILE     Send a few bytes and a break, to show that a break resets the
//              chip. Then send the seed, and each byte of the file once the
//              answer to the byte before has arrived.
// +loop=COUNT  Leave the chip to run alone until it has sent COUNT bytes.
//              Reset is held for as many clock cycles as the seed, which
//              makes that number the chip's seed.
module chip_tb;
    localparam DIVIDE = 8;
    reg clk = 0, rst = 1, loop = 0, rx = 1;
    wire tx;
    reg [31:0] seed;
    reg [8191:0] path;
    reg [7:0] b;
    integer in, out, c, count, n;

    chip #(DIVIDE) chip (clk, rst, loop, rx, tx);

    always #1 clk = ~clk;

    task send(input [7:0] value);
        integer k;
        begin
            rx <= 0;
            repeat (DIVIDE) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                rx <= value[k];
                repeat (DIVIDE) @(posedge clk);
            end
            rx <= 1;
            repeat (DIVIDE) @(posedge clk);
        end
    endtask

    task receive;
        integer k;
        begin
            @(negedge tx);
            repeat (DIVIDE / 2) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                repeat (DIVIDE) @(posedge clk);
                b[k] = tx;
            end
            repeat (DIVIDE) @(posedge clk);
            $fwrite(out, "%0d\n", b);
        end
    endtask

    initial begin
        if (!$value$plusargs("seed=%d", seed)) $finish;
        if (!$value$plusargs("out=%s", path)) $finish;
        out = $fopen(path, "w");
        if ($value$plusargs("loop=%d", count)) begin
            loop = 1;
            repeat (seed) @(posedge clk);
            rst <= 0;
            repeat (count) receive;
        end else begin
            if (!$value$plusargs("in=%s", path)) $finish;
            in = $fopen(path, "rb");
            repeat (4) @(posedge clk);
            rst <= 0;
            for (n = 0; n < 5; n = n + 1) send(n[7:0] + 8'h5a);
            rx <= 0;
            repeat (30 * DIVIDE) @(posedge clk);
            rx <= 1;
            repeat (DIVIDE) @(posedge clk);
            for (n = 0; n < 4; n = n + 1) send(seed[8 * n +: 8]);
            for (c = $fgetc(in); c >= 0; c = $fgetc(in)) begin
                fork
                    send(c[7:0]);
                    receive;
                join
            end
        end
        $finish;
    end
endmodule
