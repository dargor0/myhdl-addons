"""AXI4-Stream source/sink (AX-FR-050)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import Axi, AxiPointToPoint, axis_sink, axis_source
from myhdl_addons.axi.stream import (
    axis_sink_sidebands,
    axis_source_sidebands,
)


@block
def _tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="stream",
        interconnect=AxiPointToPoint(),
    )
    src_port = bus.add_master("src")
    snk_port = bus.add_slave(name="snk")

    din = Signal(intbv(0)[32:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rdy = Signal(bool(0))
    dout = Signal(intbv(0)[32:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rin = Signal(bool(0))

    src = axis_source(src_port, din, vin, lin, rdy)
    snk = axis_sink(snk_port, rin, dout, vout, lout)
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

        din.next = 0xDEAD
        vin.next = 1
        lin.next = 1
        rin.next = 0
        yield delay(1)
        assert int(vout) == 0  # sink not ready
        assert int(rdy) == 0

        rin.next = 1
        yield delay(1)
        assert int(vout) == 1
        assert int(rdy) == 1
        assert int(dout) == 0xDEAD
        assert int(lout) == 1

        yield aclk.posedge
        vin.next = 0
        raise StopSimulation

    return clkgen, glue, src, snk, stim


def test_axis_source_sink_loopback():
    _tb().run_sim()


@block
def _sideband_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

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
    src_port = bus.add_master("src")
    snk_port = bus.add_slave(name="snk")

    names = {
        "tstrb": 4,
        "tkeep": 4,
        "tid": 4,
        "tdest": 4,
        "tuser": 4,
    }
    ins = {n: Signal(intbv(0)[w:]) for n, w in names.items()}
    outs = {n: Signal(intbv(0)[w:]) for n, w in names.items()}

    ss = axis_source_sidebands(src_port, ins)
    sk = axis_sink_sidebands(snk_port, outs)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        aclk.next = not aclk

    @instance
    def stim():
        for i, sig in enumerate(ins.values()):
            sig.next = 0x5 + i
        yield delay(1)
        for i, sig in enumerate(outs.values()):
            assert int(sig) == 0x5 + i, (i, int(sig))
        raise StopSimulation

    return clkgen, glue, ss, sk, stim


def test_axis_sidebands_pass_through():
    _sideband_tb().run_sim()
