// The chip on a Sipeed Tang Mega 138K Dock, with the pins in
// tang-mega-138k.cst. Not yet tried on a board.
//
// The chip runs at 25 MHz, half the board's clock, since on an ECP5 it reaches
// only about 29 MHz; once Gowin's timing report shows it can, run it at 50. The
// serial port runs at 115200 baud through the board's USB bridge. Loading the
// design or pressing reset restarts the chip. With LOOP set to 1 the chip
// writes on its own, with no host.
//
// To build, make a project in the Gowin IDE for the GW5AST-LV138PG484AC1/I0
// with this file, the .cst file, ../chip.v and the permacast.v that
// compile.py writes, and put the .hex files it writes in the project folder.
module top #(parameter LOOP = 0) (
    input clk, reset_n, rx,
    output tx
);
    reg slow = 0;  // the chip's clock
    always @(posedge clk) slow <= !slow;
    reg [3:0] boot = 0;  // holds the chip in reset for its first ticks
    always @(posedge slow) if (boot != 15) boot <= boot + 1;
    chip #(217) chip (slow, boot != 15 || !reset_n, LOOP != 0, rx, tx);
endmodule
