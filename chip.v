// The chip: a compiled model behind a serial port. It works with any model
// that reads a byte and gives one output below 256.
//
// The port carries bytes as 8 data bits, no parity and 1 stop bit, and one bit
// lasts DIVIDE clock cycles.
//
// After reset the first four bytes received are the seed, lowest byte first.
// Every byte after that is one step of the model, and the chip answers with
// the model's output. Wait for the answer before sending the next byte. A
// break, rx held low for longer than two bytes, resets the chip.
//
// With loop high the chip needs no host. Its seed is the number of clock
// cycles since power-up, its first input is 0, and it sends every output and
// takes it as the next input.
module chip #(parameter DIVIDE = 434) (
    input clk, rst, loop, rx,
    output tx
);
    // Receiver. got is high for one cycle when data holds a new byte.
    reg [1:0] line = 3; // rx, brought onto the clock
    reg [23:0] low = 0; // cycles that rx has been low, up to a break
    wire reset = rst || low == 20 * DIVIDE;
    reg [15:0] rwait;   // cycles until the middle of the next bit
    reg [3:0] rbit;     // 0 when idle, 1 to 8 for the data bits, 9 for the stop bit
    reg [7:0] data;
    reg got;
    always @(posedge clk) begin
        line <= {line[0], rx};
        low <= line[1] ? 0 : reset ? low : low + 1;
        got <= 0;
        if (reset) rbit <= 0;
        else if (rbit == 0) begin
            if (!line[1]) begin rbit <= 1; rwait <= DIVIDE + DIVIDE / 2 - 1; end
        end else if (rwait != 0) rwait <= rwait - 1;
        else begin
            rwait <= DIVIDE - 1;
            rbit <= rbit == 9 ? 0 : rbit + 1;
            if (rbit == 9) got <= line[1];
            else data <= {line[1], data[7:1]};
        end
    end

    // The model, and x, its next input, which is waiting while full is high.
    reg [31:0] ticks = 0, seed;
    reg [2:0] have;     // bytes of the seed received
    reg seeded, full, start;
    reg [7:0] x;
    wire ready, valid;
    wire signed [31:0] y;
    permacast model (clk, !seeded, start, seed, {24'd0, x}, ready, valid, y);

    // Sender. Bits leave from the low end of send.
    reg [15:0] twait;
    reg [3:0] tbit;     // bits still to send
    reg [9:0] send;
    assign tx = tbit == 0 || send[0];
    always @(posedge clk) begin
        if (reset) tbit <= 0;
        else if (valid) begin send <= {1'b1, y[7:0], 1'b0}; tbit <= 10; twait <= DIVIDE - 1; end
        else if (tbit != 0) begin
            if (twait != 0) twait <= twait - 1;
            else begin send <= {1'b1, send[9:1]}; tbit <= tbit - 1; twait <= DIVIDE - 1; end
        end
    end

    always @(posedge clk) begin
        ticks <= ticks + 1;
        start <= 0;
        if (reset) begin
            have <= 0; seeded <= 0; full <= 0;
        end else if (!seeded) begin  // the model is held in reset until it has its seed
            seeded <= have == 4;
            if (loop && have != 4) begin seed <= ticks; have <= 4; x <= 0; full <= 1; end
            else if (got && have != 4) begin seed <= {data, seed[31:8]}; have <= have + 1; end
        end else begin
            if (loop ? valid : got) begin x <= loop ? y[7:0] : data; full <= 1; end
            if (full && ready && !start && tbit == 0 && !valid) begin start <= 1; full <= 0; end
        end
    end
endmodule
