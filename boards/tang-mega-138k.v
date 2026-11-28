// The chip on a Sipeed Tang Mega 138K Dock, with the pins in
// tang-mega-138k.cst. Not yet tried on a board.
//
// The chip runs on the board's 50 MHz clock, and its serial port at 115200
// baud through the board's USB bridge. Loading the design or pressing reset
// restarts the chip. With LOOP set to 1 the chip writes on its own, with no
// host.
//
// To build it with open tools (Yosys, nextpnr-himbaechel and Apicula), in the
// folder where compile.py wrote permacast.v and the .hex files:
//
//   yosys -p 'read_verilog ../boards/tang-mega-138k.v ../chip.v permacast.v;
//       synth_gowin -family gw5a -top top -json synth.json'
//   nextpnr-himbaechel --json synth.json --write pnr.json --freq 50 \
//       --device GW5AST-LV138PG484AC1/I0 --vopt family=GW5AST-138C \
//       --vopt cst=../boards/tang-mega-138k.cst
//   gowin_pack -d GW5AST-138C -o chip.fs pnr.json
//   openFPGALoader -b tangmega138k chip.fs
//
// If nextpnr reports that the chip cannot keep up with 50 MHz, it needs a
// slower clock from one of the FPGA's PLLs.
module top #(parameter LOOP = 0) (
    input clk, reset_n, rx,
    output tx
);
    reg [3:0] boot = 0;  // holds the chip in reset for its first ticks
    always @(posedge clk) if (boot != 15) boot <= boot + 1;
    chip #(434) chip (clk, boot != 15 || !reset_n, LOOP != 0, rx, tx);
endmodule
