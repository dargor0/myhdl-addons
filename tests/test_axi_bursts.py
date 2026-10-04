"""AXI burst attributes, LAST alignment and FIXED/WRAP bursts (AX-FR-027/035/100)."""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import (
    Axi,
    AxiBFM,
    AxiPointToPoint,
    AxiProtocolError,
    axi_full_slave,
    axi_master,
    check_burst,
    check_last_alignment,
)


@block
def _burst_tb(burst, size, length, data_width=32):
    clk = Signal(bool(0))
    rst = Signal(bool(1))
    valid = Signal(bool(0))
    b = Signal(intbv(0)[2:])
    s = Signal(intbv(0)[3:])
    ln = Signal(intbv(0)[8:])

    mon = check_burst(clk, rst, valid, b, s, ln, data_width=data_width, label="aw")

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 0
        yield clk.posedge
        yield clk.posedge
        rst.next = 1
        b.next = burst
        s.next = size
        ln.next = length
        valid.next = 1
        yield delay(100)
        raise StopSimulation

    return clkgen, mon, stim


def test_check_burst_valid():
    _burst_tb(burst=1, size=2, length=3).run_sim()
    _burst_tb(burst=2, size=2, length=3).run_sim()
    _burst_tb(burst=0, size=2, length=0).run_sim()


def test_check_burst_invalid_code():
    with pytest.raises(AxiProtocolError):
        _burst_tb(burst=3, size=2, length=0).run_sim()


def test_check_burst_bad_wrap_length():
    with pytest.raises(AxiProtocolError):
        _burst_tb(burst=2, size=2, length=2).run_sim()


def test_check_burst_size_exceeds_bus():
    with pytest.raises(AxiProtocolError):
        _burst_tb(burst=1, size=5, length=0, data_width=32).run_sim()


@block
def _last_tb(seq):
    clk = Signal(bool(0))
    rst = Signal(bool(1))
    valid = Signal(bool(0))
    ready = Signal(bool(1))
    last = Signal(bool(0))
    ln = Signal(intbv(2)[8:])  # 3 beats

    mon = check_last_alignment(clk, rst, valid, ready, last, ln, label="w")

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 0
        yield clk.posedge
        yield clk.posedge
        rst.next = 1
        valid.next = 1
        for value in seq:
            last.next = value
            yield clk.posedge
        valid.next = 0
        yield delay(100)
        raise StopSimulation

    return clkgen, mon, stim


def test_check_last_alignment_ok():
    _last_tb([0, 0, 1]).run_sim()


def test_check_last_alignment_premature():
    with pytest.raises(AxiProtocolError):
        _last_tb([0, 1, 0]).run_sim()


def test_check_last_alignment_missing():
    with pytest.raises(AxiProtocolError):
        _last_tb([0, 0, 0, 0]).run_sim()


@block
def _burst_rw_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")

    mem = axi_full_slave(s)
    bfm = AxiBFM(m, timeout=400)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        aclk.next = not aclk

    @instance
    def stim():
        aresetn.next = 0
        yield aclk.posedge
        yield aclk.posedge
        aresetn.next = 1

        # FIXED write: every beat targets word 1 (last one wins)
        yield bfm.write(0x04, [0x11, 0x22, 0x33], burst=0)
        yield bfm.read(0x04, 3, burst=0)
        assert bfm.last_data == [0x33, 0x33, 0x33], bfm.last_data

        # WRAP write: 4-beat wrap in the 16-byte window [0x10, 0x20)
        yield bfm.write(0x14, [0xA1, 0xA2, 0xA3, 0xA4], burst=2)
        yield bfm.read(0x00, 8)
        assert bfm.last_data == [0, 0x33, 0, 0, 0xA4, 0xA1, 0xA2, 0xA3], bfm.last_data

        # WRAP read from the same window
        yield bfm.read(0x14, 4, burst=2)
        assert bfm.last_data == [0xA1, 0xA2, 0xA3, 0xA4], bfm.last_data

        raise StopSimulation

    return clkgen, glue, mem, stim


def test_axi_full_fixed_and_wrap_bursts():
    _burst_rw_tb().run_sim()


@block
def _master_burst_tb(seen):
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")
    mem = axi_full_slave(s)

    burst = Signal(intbv(2)[2:])
    start = Signal(bool(0))
    write = Signal(bool(1))
    addr = Signal(intbv(0)[16:])
    length = Signal(intbv(0)[8:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    wvalid = Signal(bool(0))
    wready = Signal(bool(0))
    rdata = Signal(intbv(0)[32:])
    rvalid = Signal(bool(0))
    rready = Signal(bool(0))
    busy = Signal(bool(0))
    done = Signal(bool(0))

    master = axi_master(
        m,
        start,
        write,
        addr,
        length,
        wdata,
        wstrb,
        wvalid,
        wready,
        rdata,
        rvalid,
        rready,
        busy,
        done,
        burst=burst,
    )
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        aclk.next = not aclk

    @instance
    def stim():
        aresetn.next = 0
        yield aclk.posedge
        yield aclk.posedge
        aresetn.next = 1
        yield delay(1)
        seen.append(int(m.awburst))
        seen.append(int(m.arburst))
        raise StopSimulation

    return clkgen, glue, mem, master, stim


def test_axi_master_forwards_burst_code():
    seen = []
    _master_burst_tb(seen).run_sim()
    assert seen == [2, 2]
