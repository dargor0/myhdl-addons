"""AXI4-Stream utility blocks (AX-FR-052)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import (
    axis_gate,
    axis_packet_counter,
    axis_periodic_gate,
    axis_register_slice,
    axis_width_down,
    axis_width_up,
)


@block
def _register_slice_tb(results):
    clk = Signal(bool(0))
    resetn = Signal(bool(0))
    din = Signal(intbv(0)[8:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rin = Signal(bool(0))
    dout = Signal(intbv(0)[8:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rout = Signal(bool(0))

    dut = axis_register_slice(clk, resetn, din, vin, lin, rin, dout, vout, lout, rout)

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        resetn.next = 0
        yield clk.posedge
        yield clk.posedge
        resetn.next = 1
        rout.next = 1
        din.next = 0x11
        vin.next = 1
        lin.next = 1
        yield clk.posedge
        yield delay(1)
        results.append((int(vout), int(dout), int(lout)))
        vin.next = 0
        yield clk.posedge
        yield delay(1)
        results.append((int(vout), int(dout)))
        raise StopSimulation

    return clkgen, dut, stim


def test_register_slice_registers_the_beat():
    results = []
    _register_slice_tb(results).run_sim()
    assert results[0] == (1, 0x11, 1)
    assert results[1][0] == 0


@block
def _gate_tb(results):
    din = Signal(intbv(0)[8:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rin = Signal(bool(0))
    dout = Signal(intbv(0)[8:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rout = Signal(bool(0))
    enable = Signal(bool(0))

    dut = axis_gate(din, vin, lin, rin, dout, vout, lout, rout, enable)

    @instance
    def stim():
        din.next = 0x7
        vin.next = 1
        lin.next = 1
        rout.next = 0
        enable.next = 0
        yield delay(1)
        results.append((int(vout), int(rin)))  # dropped, upstream free
        enable.next = 1
        yield delay(1)
        results.append((int(vout), int(dout), int(lout), int(rin)))
        raise StopSimulation

    return dut, stim


def test_gate_blocks_and_passes():
    results = []
    _gate_tb(results).run_sim()
    assert results[0] == (0, 1)
    assert results[1] == (1, 0x7, 1, 0)


@block
def _periodic_gate_tb(samples):
    clk = Signal(bool(0))
    resetn = Signal(bool(0))
    din = Signal(intbv(0)[8:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rin = Signal(bool(0))
    dout = Signal(intbv(0)[8:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rout = Signal(bool(0))

    dut = axis_periodic_gate(
        clk, resetn, din, vin, lin, rin, dout, vout, lout, rout, period=2
    )

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        resetn.next = 0
        yield clk.posedge
        yield clk.posedge
        resetn.next = 1
        rout.next = 1
        din.next = 0x55
        vin.next = 1
        lin.next = 0
        for _ in range(6):
            yield clk.posedge
            yield delay(1)
            samples.append(int(vout))
        raise StopSimulation

    return clkgen, dut, stim


def test_periodic_gate_passes_every_other_cycle():
    samples = []
    _periodic_gate_tb(samples).run_sim()
    assert sum(samples) == 3
    assert samples == [0, 1, 0, 1, 0, 1]


@block
def _width_down_tb(results):
    clk = Signal(bool(0))
    resetn = Signal(bool(0))
    din = Signal(intbv(0)[32:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rin = Signal(bool(0))
    dout = Signal(intbv(0)[16:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rout = Signal(bool(0))

    dut = axis_width_down(clk, resetn, din, vin, lin, rin, dout, vout, lout, rout)

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        resetn.next = 0
        yield clk.posedge
        yield clk.posedge
        resetn.next = 1
        rout.next = 1
        din.next = 0xAAAABBBB
        vin.next = 1
        lin.next = 1
        yield clk.posedge
        yield delay(1)
        results.append((int(vout), int(dout), int(lout)))
        yield clk.posedge
        yield delay(1)
        results.append((int(vout), int(dout), int(lout)))
        yield clk.posedge
        yield delay(1)
        results.append((int(vout),))
        raise StopSimulation

    return clkgen, dut, stim


def test_width_down_splits_into_sub_beats():
    results = []
    _width_down_tb(results).run_sim()
    assert results[0] == (1, 0xBBBB, 0)
    assert results[1] == (1, 0xAAAA, 1)
    assert results[2] == (0,)


@block
def _width_up_tb(results):
    clk = Signal(bool(0))
    resetn = Signal(bool(0))
    din = Signal(intbv(0)[16:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rin = Signal(bool(0))
    dout = Signal(intbv(0)[32:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rout = Signal(bool(0))

    dut = axis_width_up(clk, resetn, din, vin, lin, rin, dout, vout, lout, rout)

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        resetn.next = 0
        yield clk.posedge
        yield clk.posedge
        resetn.next = 1
        rout.next = 1
        din.next = 0xBBBB
        vin.next = 1
        lin.next = 0
        yield clk.posedge
        yield delay(1)
        results.append((int(vout),))
        din.next = 0xAAAA
        lin.next = 1
        yield clk.posedge
        yield delay(1)
        results.append((int(vout), int(dout), int(lout)))
        yield clk.posedge
        yield delay(1)
        results.append((int(vout),))
        raise StopSimulation

    return clkgen, dut, stim


def test_width_up_merges_sub_beats():
    results = []
    _width_up_tb(results).run_sim()
    assert results[0] == (0,)
    assert results[1] == (1, 0xAAAABBBB, 1)
    assert results[2] == (0,)


@block
def _packet_counter_tb(results):
    clk = Signal(bool(0))
    resetn = Signal(bool(0))
    valid = Signal(bool(0))
    ready = Signal(bool(0))
    last = Signal(bool(0))
    beats = Signal(intbv(0)[8:])
    packets = Signal(intbv(0)[8:])

    dut = axis_packet_counter(clk, resetn, valid, ready, last, beats, packets)

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        resetn.next = 0
        yield clk.posedge
        yield clk.posedge
        resetn.next = 1
        ready.next = 1
        valid.next = 1
        last.next = 0
        yield clk.posedge
        last.next = 1
        yield clk.posedge
        valid.next = 0
        yield clk.posedge
        results.append((int(beats), int(packets)))
        raise StopSimulation

    return clkgen, dut, stim


def test_packet_counter_counts_beats_and_packets():
    results = []
    _packet_counter_tb(results).run_sim()
    assert results[0] == (2, 1)
