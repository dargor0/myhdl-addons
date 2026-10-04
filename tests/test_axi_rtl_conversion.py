"""Conversion smoke tests for the AXI RTL blocks (Verilog + VHDL).

Each synthesizable core is elaborated as a *closed* system: a real counterpart
drives and reads every port through the point-to-point fabric, all external
command/status signals are top-level ports, and the AXI attributes / response
IDs that a simple core legitimately ignores are still sampled by a monitor, so
nothing is left undriven or unread and conversion is clean.
"""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.axi import (
    Axi,
    AxiLiteCSR,
    AxiPointToPoint,
    axi_full_slave,
    axi_full_slave_oo,
    axi_lite_master,
    axi_master,
    axis_gate,
    axis_packet_counter,
    axis_periodic_gate,
    axis_register_slice,
    axis_sink,
    axis_source,
    axis_width_down,
    axis_width_up,
)
from myhdl_addons.axi.stream import axis_sink_sidebands, axis_source_sidebands

HDLS = ["Verilog", "VHDL"]


# -- AXI4 full: master <-> memory slave ------------------------------------
@block
def _full_top(
    aclk,
    aresetn,
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
    observe,
):
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")
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
    )
    slave = axi_full_slave(s)
    glue = bus.build()

    @always_comb
    def monitor():
        observe.next = 0
        if s.awsize != 0:
            observe.next = 1
        if s.awlock:
            observe.next = 1
        if s.awcache != 0:
            observe.next = 1
        if s.awprot != 0:
            observe.next = 1
        if s.arsize != 0:
            observe.next = 1
        if s.arlock:
            observe.next = 1
        if s.arcache != 0:
            observe.next = 1
        if s.arprot != 0:
            observe.next = 1
        if m.bid != 0:
            observe.next = 1
        if m.bresp != 0:
            observe.next = 1
        if m.rid != 0:
            observe.next = 1
        if m.rresp != 0:
            observe.next = 1

    return master, slave, glue, monitor


def _full_signals():
    return (
        Signal(bool(0)),  # aclk
        Signal(bool(0)),  # aresetn
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
        Signal(bool(0)),  # observe
    )


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_full_master_slave_converts(hdl, convert_dut):
    convert_dut(_full_top(*_full_signals()), hdl, f"axi_full_{hdl.lower()}")


# -- AXI4 full: master <-> outstanding-read slave --------------------------
@block
def _full_oo_top(
    aclk,
    aresetn,
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
    observe,
):
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")
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
    )
    slave = axi_full_slave_oo(s, depth=4)
    glue = bus.build()

    @always_comb
    def monitor():
        observe.next = 0
        if s.awlen != 0:
            observe.next = 1
        if s.awburst != 0:
            observe.next = 1
        if s.arburst != 0:
            observe.next = 1
        if s.awsize != 0:
            observe.next = 1
        if s.awlock:
            observe.next = 1
        if s.awcache != 0:
            observe.next = 1
        if s.awprot != 0:
            observe.next = 1
        if s.arsize != 0:
            observe.next = 1
        if s.arlock:
            observe.next = 1
        if s.arcache != 0:
            observe.next = 1
        if s.arprot != 0:
            observe.next = 1
        if m.bid != 0:
            observe.next = 1
        if m.bresp != 0:
            observe.next = 1
        if m.rid != 0:
            observe.next = 1
        if m.rresp != 0:
            observe.next = 1

    return master, slave, glue, monitor


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_full_slave_oo_converts(hdl, convert_dut):
    convert_dut(_full_oo_top(*_full_signals()), hdl, f"axi_full_oo_{hdl.lower()}")


# -- AXI4-Lite: master <-> CSR --------------------------------------------
@block
def _lite_top(
    aclk,
    aresetn,
    start,
    write,
    addr,
    wdata,
    wstrb,
    busy,
    done,
    rdata,
    resp,
    status_in,
    strobes,
    observe,
):
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="lite",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="csr")
    master = axi_lite_master(
        m, start, write, addr, wdata, wstrb, busy, done, rdata, resp
    )

    csr = AxiLiteCSR(width=32)
    csr.add_write(0x00, "CTRL", init=1)
    csr.add_ro(0x04, "ID", init=0xCAFE)
    csr.add_read(0x08, "STATUS")
    peri = csr.build(s)

    glue = bus.build()
    status = csr.signals["STATUS"]
    wr_ctrl, rd_ctrl = csr.wr["CTRL"], csr.rd["CTRL"]
    wr_id, rd_id = csr.wr["ID"], csr.rd["ID"]
    wr_status, rd_status = csr.wr["STATUS"], csr.rd["STATUS"]

    @always_comb
    def drive_status():
        status.next = status_in

    @always_comb
    def collect_strobes():
        strobes.next = wr_ctrl or rd_ctrl or wr_id or rd_id or wr_status or rd_status

    @always_comb
    def monitor():
        # the CSR ignores the AXI protection attributes: sample them so the
        # forwarded signals are read.
        observe.next = 0
        if s.awprot != 0:
            observe.next = 1
        if s.arprot != 0:
            observe.next = 1

    return master, peri, glue, drive_status, collect_strobes, monitor


@pytest.mark.parametrize("hdl", HDLS)
def test_axi_lite_master_csr_converts(hdl, convert_dut):
    dut = _lite_top(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[16:]),
        Signal(intbv(0)[32:]),
        Signal(intbv(0)[4:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(intbv(0)[2:]),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    convert_dut(dut, hdl, f"axi_lite_{hdl.lower()}")


# -- AXI4-Stream: source <-> sink, with sidebands and a counter ------------
@block
def _axis_top(
    aclk,
    aresetn,
    din,
    vin,
    lin,
    rin,
    dout,
    vout,
    lout,
    rout,
    tstrb_i,
    tkeep_i,
    tid_i,
    tdest_i,
    tuser_i,
    tstrb_o,
    tkeep_o,
    tid_o,
    tdest_o,
    tuser_o,
    beats,
    packets,
):
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        user_width=4,
        variant="stream",
        user=True,
        interconnect=AxiPointToPoint(),
    )
    src = bus.add_master("src")
    snk = bus.add_slave(name="snk")
    source = axis_source(src, din, vin, lin, rout)
    sink = axis_sink(snk, rin, dout, vout, lout)
    ins = {
        "tstrb": tstrb_i,
        "tkeep": tkeep_i,
        "tid": tid_i,
        "tdest": tdest_i,
        "tuser": tuser_i,
    }
    outs = {
        "tstrb": tstrb_o,
        "tkeep": tkeep_o,
        "tid": tid_o,
        "tdest": tdest_o,
        "tuser": tuser_o,
    }
    src_sb = axis_source_sidebands(src, ins)
    snk_sb = axis_sink_sidebands(snk, outs)
    counter = axis_packet_counter(aclk, aresetn, vout, rin, lout, beats, packets)
    glue = bus.build()
    return source, sink, src_sb, snk_sb, counter, glue


@pytest.mark.parametrize("hdl", HDLS)
def test_axis_source_sink_converts(hdl, convert_dut):
    sigs = [Signal(intbv(0)[4:]) for _ in range(10)]
    dut = _axis_top(
        Signal(bool(0)),  # aclk
        Signal(bool(0)),  # aresetn
        Signal(intbv(0)[32:]),  # din
        Signal(bool(0)),  # vin
        Signal(bool(0)),  # lin
        Signal(bool(0)),  # rin
        Signal(intbv(0)[32:]),  # dout
        Signal(bool(0)),  # vout
        Signal(bool(0)),  # lout
        Signal(bool(0)),  # rout
        *sigs,  # sidebands in + out
        Signal(intbv(0)[32:]),  # beats
        Signal(intbv(0)[32:]),  # packets
    )
    convert_dut(dut, hdl, f"axis_{hdl.lower()}")


# -- AXI4-Stream utilities (plain signal interfaces) ----------------------
@pytest.mark.parametrize("hdl", HDLS)
def test_axis_register_slice_converts(hdl, convert_dut):
    dut = axis_register_slice(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    convert_dut(dut, hdl, f"axis_reg_slice_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axis_gate_converts(hdl, convert_dut):
    dut = axis_gate(
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    convert_dut(dut, hdl, f"axis_gate_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axis_periodic_gate_converts(hdl, convert_dut):
    dut = axis_periodic_gate(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        period=4,
    )
    convert_dut(dut, hdl, f"axis_periodic_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axis_width_down_converts(hdl, convert_dut):
    dut = axis_width_down(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[8:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    convert_dut(dut, hdl, f"axis_wdown_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axis_width_up_converts(hdl, convert_dut):
    dut = axis_width_up(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[8:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    convert_dut(dut, hdl, f"axis_wup_{hdl.lower()}")


@pytest.mark.parametrize("hdl", HDLS)
def test_axis_packet_counter_converts(hdl, convert_dut):
    dut = axis_packet_counter(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(intbv(0)[32:]),
    )
    convert_dut(dut, hdl, f"axis_pktcount_{hdl.lower()}")
