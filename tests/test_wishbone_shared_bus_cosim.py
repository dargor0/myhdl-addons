"""Verilog cosimulation smoke test for the Wishbone shared-bus fabric (Option A).

A single master drives the shared-bus fabric to two CSR slaves; the same
clocked bench drives either the Python instances or the converted Verilog RTL
bound to an equivalent ``SignalView`` and the read-back data must match.
"""

from myhdl import (
    Signal,
    StopSimulation,
    always,
    always_comb,
    block,
    delay,
    instance,
    intbv,
)

from myhdl_addons.common.views import SignalView
from myhdl_addons.wishbone import CSRMap, SharedBus, Wishbone, wishbone_master


@block
def _shared_top(
    clk,
    rst,
    req,
    adr,
    we,
    dat_w,
    sel,
    busy,
    done,
    dat_r,
    err,
    s0_strobes,
    s1_strobes,
):
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=SharedBus()
    )
    p0 = bus.add_master("m0")
    sp0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    sp1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    master = wishbone_master(p0, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    csr0 = CSRMap(width=32)
    csr0.add_write(0x00, "REG", init=1)
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    csr1 = CSRMap(width=32)
    csr1.add_write(0x00, "REG", init=2)
    csr1.add_ro(0x04, "ID", init=0xBBBB)
    peri0 = csr0.build(sp0)
    peri1 = csr1.build(sp1)
    glue = bus.build()

    wr0, rd0 = csr0.wr["REG"], csr0.rd["REG"]
    wr0b, rd0b = csr0.wr["ID"], csr0.rd["ID"]
    wr1, rd1 = csr1.wr["REG"], csr1.rd["REG"]
    wr1b, rd1b = csr1.wr["ID"], csr1.rd["ID"]

    @always_comb
    def collect0():
        s0_strobes.next = wr0 or rd0 or wr0b or rd0b

    @always_comb
    def collect1():
        s1_strobes.next = wr1 or rd1 or wr1b or rd1b

    return [master, peri0, peri1, glue, collect0, collect1]


def _ports():
    return SignalView(
        clk=Signal(bool(0)),
        rst=Signal(bool(0)),
        req=Signal(bool(0)),
        adr=Signal(intbv(0)[16:]),
        we=Signal(bool(0)),
        dat_w=Signal(intbv(0)[32:]),
        sel=Signal(intbv(0)[4:]),
        busy=Signal(bool(0)),
        done=Signal(bool(0)),
        dat_r=Signal(intbv(0)[32:]),
        err=Signal(bool(0)),
        s0_strobes=Signal(bool(0)),
        s1_strobes=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _shared_top(
        ports.clk,
        ports.rst,
        ports.req,
        ports.adr,
        ports.we,
        ports.dat_w,
        ports.sel,
        ports.busy,
        ports.done,
        ports.dat_r,
        ports.err,
        ports.s0_strobes,
        ports.s1_strobes,
    )


@block
def _bench(make_dut, ports, results):
    dut = make_dut(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.rst.next = 1
        yield ports.clk.posedge
        yield delay(1)
        ports.rst.next = 0
        yield delay(1)

        # read ID from both slaves
        ports.req.next = 1
        ports.we.next = 0
        ports.adr.next = 0x04
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("id0a", int(ports.busy)))
        ports.req.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(("id0b", int(ports.done), int(ports.dat_r)))

        ports.req.next = 1
        ports.we.next = 0
        ports.adr.next = 0x1004
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("id1a", int(ports.busy)))
        ports.req.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(("id1b", int(ports.done), int(ports.dat_r)))

        # write REG in slave0 and read it back
        ports.req.next = 1
        ports.we.next = 1
        ports.adr.next = 0x00
        ports.dat_w.next = 0xBEEF
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("wr0a", int(ports.busy)))
        ports.req.next = 0
        ports.we.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(("wr0b", int(ports.done)))

        ports.req.next = 1
        ports.we.next = 0
        ports.adr.next = 0x00
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("rd0a", int(ports.busy)))
        ports.req.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(("rd0b", int(ports.done), int(ports.dat_r)))
        raise StopSimulation

    return dut, clkgen, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_wishbone_shared_bus_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "wb_shared_cosim")

    assert _run(cosim) == _run(_dut)
