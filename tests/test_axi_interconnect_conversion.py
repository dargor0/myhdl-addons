"""Conversion smoke tests for the AXI fabric strategies (Verilog + VHDL).

Each strategy is elaborated as a closed 2-master / 2-slave system: real AXI
master and slave cores drive and read every fabric port, the externally-sourced
CSR register is driven, the per-register strobes are consumed, and the AXI
attributes / response IDs that the simple cores ignore are sampled by a monitor.
Nothing is left undriven or unread, so conversion is clean.
"""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.axi import (
    Axi,
    AxiCrossbar,
    AxiLiteCSR,
    AxiSharedBus,
    axi_full_slave,
    axi_lite_master,
    axi_master,
)

HDLS = ["Verilog", "VHDL"]


@block
def lite_system(aclk, aresetn, ic, m0, m1, s0_strobes, s1_strobes, observe):
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="lite",
        interconnect=ic,
    )
    p0 = bus.add_master("m0")
    p1 = bus.add_master("m1")
    sp0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    sp1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    master0 = axi_lite_master(p0, *m0)
    master1 = axi_lite_master(p1, *m1)

    csr0 = AxiLiteCSR(width=32)
    csr0.add_write(0x00, "REG", init=1)
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    csr1 = AxiLiteCSR(width=32)
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

    @always_comb
    def monitor():
        observe.next = 0
        if sp0.awprot != 0:
            observe.next = 1
        if sp0.arprot != 0:
            observe.next = 1
        if sp1.awprot != 0:
            observe.next = 1
        if sp1.arprot != 0:
            observe.next = 1

    return [master0, master1, peri0, peri1, glue, collect0, collect1, monitor]


@block
def full_system(aclk, aresetn, ic, m0, m1, observe):
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=ic,
    )
    p0 = bus.add_master("m0")
    p1 = bus.add_master("m1")
    sp0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    sp1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    master0 = axi_master(p0, *m0)
    master1 = axi_master(p1, *m1)
    slave0 = axi_full_slave(sp0)
    slave1 = axi_full_slave(sp1)
    glue = bus.build()

    @always_comb
    def monitor():
        observe.next = 0
        if sp0.awsize != 0:
            observe.next = 1
        if sp0.awlock:
            observe.next = 1
        if sp0.awcache != 0:
            observe.next = 1
        if sp0.awprot != 0:
            observe.next = 1
        if sp0.arsize != 0:
            observe.next = 1
        if sp0.arlock:
            observe.next = 1
        if sp0.arcache != 0:
            observe.next = 1
        if sp0.arprot != 0:
            observe.next = 1
        if sp1.awsize != 0:
            observe.next = 1
        if sp1.awlock:
            observe.next = 1
        if sp1.awcache != 0:
            observe.next = 1
        if sp1.awprot != 0:
            observe.next = 1
        if sp1.arsize != 0:
            observe.next = 1
        if sp1.arlock:
            observe.next = 1
        if sp1.arcache != 0:
            observe.next = 1
        if sp1.arprot != 0:
            observe.next = 1
        if p0.bid != 0:
            observe.next = 1
        if p0.bresp != 0:
            observe.next = 1
        if p0.rid != 0:
            observe.next = 1
        if p0.rresp != 0:
            observe.next = 1
        if p1.bid != 0:
            observe.next = 1
        if p1.bresp != 0:
            observe.next = 1
        if p1.rid != 0:
            observe.next = 1
        if p1.rresp != 0:
            observe.next = 1

    return [master0, master1, slave0, slave1, glue, monitor]


@block
def _shared_lite_top(
    aclk,
    aresetn,
    m0_start,
    m0_write,
    m0_addr,
    m0_wdata,
    m0_wstrb,
    m0_busy,
    m0_done,
    m0_rdata,
    m0_resp,
    m1_start,
    m1_write,
    m1_addr,
    m1_wdata,
    m1_wstrb,
    m1_busy,
    m1_done,
    m1_rdata,
    m1_resp,
    s0_strobes,
    s1_strobes,
    observe,
):
    m0 = (
        m0_start,
        m0_write,
        m0_addr,
        m0_wdata,
        m0_wstrb,
        m0_busy,
        m0_done,
        m0_rdata,
        m0_resp,
    )
    m1 = (
        m1_start,
        m1_write,
        m1_addr,
        m1_wdata,
        m1_wstrb,
        m1_busy,
        m1_done,
        m1_rdata,
        m1_resp,
    )
    return lite_system(
        aclk, aresetn, AxiSharedBus(), m0, m1, s0_strobes, s1_strobes, observe
    )


@block
def _cross_lite_top(
    aclk,
    aresetn,
    m0_start,
    m0_write,
    m0_addr,
    m0_wdata,
    m0_wstrb,
    m0_busy,
    m0_done,
    m0_rdata,
    m0_resp,
    m1_start,
    m1_write,
    m1_addr,
    m1_wdata,
    m1_wstrb,
    m1_busy,
    m1_done,
    m1_rdata,
    m1_resp,
    s0_strobes,
    s1_strobes,
    observe,
):
    m0 = (
        m0_start,
        m0_write,
        m0_addr,
        m0_wdata,
        m0_wstrb,
        m0_busy,
        m0_done,
        m0_rdata,
        m0_resp,
    )
    m1 = (
        m1_start,
        m1_write,
        m1_addr,
        m1_wdata,
        m1_wstrb,
        m1_busy,
        m1_done,
        m1_rdata,
        m1_resp,
    )
    return lite_system(
        aclk, aresetn, AxiCrossbar(), m0, m1, s0_strobes, s1_strobes, observe
    )


@block
def _shared_full_top(
    aclk,
    aresetn,
    m0_start,
    m0_write,
    m0_addr,
    m0_length,
    m0_wdata,
    m0_wstrb,
    m0_wvalid,
    m0_wready,
    m0_rdata,
    m0_rvalid,
    m0_rready,
    m0_busy,
    m0_done,
    m1_start,
    m1_write,
    m1_addr,
    m1_length,
    m1_wdata,
    m1_wstrb,
    m1_wvalid,
    m1_wready,
    m1_rdata,
    m1_rvalid,
    m1_rready,
    m1_busy,
    m1_done,
    observe,
):
    m0 = (
        m0_start,
        m0_write,
        m0_addr,
        m0_length,
        m0_wdata,
        m0_wstrb,
        m0_wvalid,
        m0_wready,
        m0_rdata,
        m0_rvalid,
        m0_rready,
        m0_busy,
        m0_done,
    )
    m1 = (
        m1_start,
        m1_write,
        m1_addr,
        m1_length,
        m1_wdata,
        m1_wstrb,
        m1_wvalid,
        m1_wready,
        m1_rdata,
        m1_rvalid,
        m1_rready,
        m1_busy,
        m1_done,
    )
    return full_system(aclk, aresetn, AxiSharedBus(), m0, m1, observe)


@block
def _cross_full_top(
    aclk,
    aresetn,
    m0_start,
    m0_write,
    m0_addr,
    m0_length,
    m0_wdata,
    m0_wstrb,
    m0_wvalid,
    m0_wready,
    m0_rdata,
    m0_rvalid,
    m0_rready,
    m0_busy,
    m0_done,
    m1_start,
    m1_write,
    m1_addr,
    m1_length,
    m1_wdata,
    m1_wstrb,
    m1_wvalid,
    m1_wready,
    m1_rdata,
    m1_rvalid,
    m1_rready,
    m1_busy,
    m1_done,
    observe,
):
    m0 = (
        m0_start,
        m0_write,
        m0_addr,
        m0_length,
        m0_wdata,
        m0_wstrb,
        m0_wvalid,
        m0_wready,
        m0_rdata,
        m0_rvalid,
        m0_rready,
        m0_busy,
        m0_done,
    )
    m1 = (
        m1_start,
        m1_write,
        m1_addr,
        m1_length,
        m1_wdata,
        m1_wstrb,
        m1_wvalid,
        m1_wready,
        m1_rdata,
        m1_rvalid,
        m1_rready,
        m1_busy,
        m1_done,
    )
    return full_system(aclk, aresetn, AxiCrossbar(), m0, m1, observe)


def _lite_signals():
    def master():
        return (
            Signal(bool(0)),  # start
            Signal(bool(0)),  # write
            Signal(intbv(0)[16:]),  # addr
            Signal(intbv(0)[32:]),  # wdata
            Signal(intbv(0)[4:]),  # wstrb
            Signal(bool(0)),  # busy
            Signal(bool(0)),  # done
            Signal(intbv(0)[32:]),  # rdata
            Signal(intbv(0)[2:]),  # resp
        )

    return (
        Signal(bool(0)),
        Signal(bool(0)),
        *master(),
        *master(),
        Signal(bool(0)),  # s0 strobes
        Signal(bool(0)),  # s1 strobes
        Signal(bool(0)),  # observe
    )


def _full_signals():
    def master():
        return (
            Signal(bool(0)),  # start
            Signal(bool(0)),  # write
            Signal(intbv(0)[16:]),  # addr
            Signal(intbv(0)[8:]),  # length
            Signal(intbv(0)[32:]),  # wdata
            Signal(intbv(0)[4:]),  # wstrb
            Signal(bool(0)),  # wvalid
            Signal(bool(0)),  # wready
            Signal(intbv(0)[32:]),  # rdata
            Signal(bool(0)),  # rvalid
            Signal(bool(0)),  # rready
            Signal(bool(0)),  # busy
            Signal(bool(0)),  # done
        )

    return (
        Signal(bool(0)),
        Signal(bool(0)),
        *master(),
        *master(),
        Signal(bool(0)),  # observe
    )


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_shared_bus_lite_converts(hdl, convert_dut):
    dut = _shared_lite_top(*_lite_signals())
    convert_dut(dut, hdl, f"axi_shared_lite_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_crossbar_lite_converts(hdl, convert_dut):
    dut = _cross_lite_top(*_lite_signals())
    convert_dut(dut, hdl, f"axi_cross_lite_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_shared_bus_full_converts(hdl, convert_dut):
    dut = _shared_full_top(*_full_signals())
    convert_dut(dut, hdl, f"axi_shared_full_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_crossbar_full_converts(hdl, convert_dut):
    dut = _cross_full_top(*_full_signals())
    convert_dut(dut, hdl, f"axi_cross_full_{hdl.lower()}")
