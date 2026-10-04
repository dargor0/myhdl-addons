"""Bus-functional-model tests: timeout and error paths (WB-FR-081)."""

import pytest
from myhdl import Signal, StopSimulation, always, always_comb, block, delay, instance

from myhdl_addons.wishbone import PointToPoint, Wishbone, WishboneBFM
from myhdl_addons.wishbone.checks import WishboneError


@block
def _timeout_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=PointToPoint()
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="dead")

    @always_comb
    def dead_slave():
        active = s.cyc_i & s.stb_i
        s.ack_o.next = active & 0
        s.dat_o.next = 0

    bfm = WishboneBFM(m, timeout=5)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0
        yield bfm.read(0x00)
        raise StopSimulation

    return clkgen, glue, dead_slave, stim


def test_bfm_timeout_raises():
    with pytest.raises(WishboneError):
        _timeout_tb().run_sim()


@block
def _error_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk,
        rst,
        data_width=32,
        adr_width=16,
        gran=8,
        err=True,
        interconnect=PointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="err")

    @always_comb
    def err_slave():
        active = s.cyc_i and s.stb_i
        s.ack_o.next = 0
        s.err_o.next = active
        s.dat_o.next = 0

    bfm = WishboneBFM(m, timeout=50)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0
        yield bfm.write(0x00, 0x1234)
        raise StopSimulation

    return clkgen, glue, err_slave, stim


def test_bfm_error_raises():
    with pytest.raises(WishboneError):
        _error_tb().run_sim()


@block
def _trace_tb(seen):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk,
        rst,
        data_width=32,
        adr_width=16,
        gran=8,
        trace=True,
        interconnect=PointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x100, name="p")

    @always_comb
    def rd_slave():
        s.ack_o.next = s.cyc_i and s.stb_i
        s.dat_o.next = 0x33

    bfm = WishboneBFM(m, trace=bus.trace)
    bus.trace.transaction(seen.append)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0
        yield bfm.read(0x08, sel=0x3)
        raise StopSimulation

    return clkgen, glue, rd_slave, stim


def test_bfm_emits_transaction_records():
    seen = []
    _trace_tb(seen).run_sim()
    assert len(seen) == 1
    rec = seen[0]
    assert rec.address == 0x08
    assert rec.we is False
    assert rec.read_data == 0x33
    assert rec.response == "ack"
    assert rec.sel == 0x3
