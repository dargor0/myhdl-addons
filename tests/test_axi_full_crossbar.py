"""Full AXI4 crossbar with ID remapping and response routing (AX-FR-060/062)."""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import (
    Axi,
    AxiBFM,
    AxiConfigError,
    AxiCrossbar,
    AxiStatus,
    axi_full_slave,
)


@block
def _single_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiCrossbar(),
    )
    m0 = bus.add_master("m0")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")

    mem0 = axi_full_slave(s0)
    bfm0 = AxiBFM(m0, timeout=400, id=3)
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

        yield bfm0.write(0x0000, [0x1111, 0x2222, 0x3333])
        assert bfm0.last_resp is AxiStatus.OKAY
        assert bfm0.last_bid == 3
        yield bfm0.read(0x0000, 3)
        assert bfm0.last_data == [0x1111, 0x2222, 0x3333]
        assert bfm0.last_rid == 3

        raise StopSimulation

    return clkgen, glue, mem0, stim


def test_axi_full_crossbar_single_master_id_echo():
    _single_tb().run_sim()


@block
def _mesh_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiCrossbar(),
    )
    m0 = bus.add_master("m0")
    m1 = bus.add_master("m1")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    s1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    mem0 = axi_full_slave(s0)
    mem1 = axi_full_slave(s1)
    bfm0 = AxiBFM(m0, timeout=400, id=1)
    bfm1 = AxiBFM(m1, timeout=400, id=2)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        aclk.next = not aclk

    @instance
    def do_reset():
        aresetn.next = 0
        yield aclk.posedge
        yield aclk.posedge
        aresetn.next = 1

    @instance
    def driver0():
        while not aresetn:
            yield aclk.posedge
        yield bfm0.write(0x0000, [0xAAAA, 0xBBBB])
        assert bfm0.last_bid == 1
        yield bfm0.read(0x0000, 2)
        assert bfm0.last_data == [0xAAAA, 0xBBBB]
        assert bfm0.last_rid == 1

    @instance
    def driver1():
        while not aresetn:
            yield aclk.posedge
        yield bfm1.write(0x1000, [0xCCCC])
        assert bfm1.last_bid == 2
        yield bfm1.read(0x1000, 1)
        assert bfm1.last_data == [0xCCCC]
        assert bfm1.last_rid == 2

    @instance
    def stopper():
        yield delay(20000)
        raise StopSimulation

    return clkgen, glue, mem0, mem1, do_reset, driver0, driver1, stopper


def test_axi_full_crossbar_mesh():
    _mesh_tb().run_sim()


@block
def _shared_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiCrossbar(),
    )
    m0 = bus.add_master("m0")
    m1 = bus.add_master("m1")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")

    mem0 = axi_full_slave(s0)
    bfm0 = AxiBFM(m0, timeout=400, id=1)
    bfm1 = AxiBFM(m1, timeout=400, id=2)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        aclk.next = not aclk

    @instance
    def do_reset():
        aresetn.next = 0
        yield aclk.posedge
        yield aclk.posedge
        aresetn.next = 1

    @instance
    def driver0():
        while not aresetn:
            yield aclk.posedge
        yield bfm0.write(0x0000, [0x1111, 0x2222, 0x3333])
        assert bfm0.last_bid == 1
        yield bfm0.read(0x0000, 3)
        assert bfm0.last_data == [0x1111, 0x2222, 0x3333]
        assert bfm0.last_rid == 1

    @instance
    def driver1():
        while not aresetn:
            yield aclk.posedge
        yield bfm1.write(0x0010, [0xBBBB])
        assert bfm1.last_bid == 2
        yield bfm1.read(0x0010, 1)
        assert bfm1.last_data == [0xBBBB]
        assert bfm1.last_rid == 2

    @instance
    def stopper():
        yield delay(20000)
        raise StopSimulation

    return clkgen, glue, mem0, do_reset, driver0, driver1, stopper


def test_axi_full_crossbar_shared_slave_arbitration():
    _shared_tb().run_sim()


@block
def _dec_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiCrossbar(),
    )
    m0 = bus.add_master("m0")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")

    mem0 = axi_full_slave(s0)
    bfm0 = AxiBFM(m0, timeout=50)
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

        yield bfm0.read(0x8000)  # unmapped
        assert bfm0.last_resp is AxiStatus.DECERR
        yield bfm0.write(0x8000, [0x1234])  # unmapped
        assert bfm0.last_resp is AxiStatus.DECERR

        raise StopSimulation

    return clkgen, glue, mem0, stim


def test_axi_full_crossbar_default_slave_decerr():
    _dec_tb().run_sim()


def test_full_crossbar_rejects_small_id_width():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=1,  # 2 unique IDs < 3 masters
        variant="full",
        interconnect=AxiCrossbar(),
    )
    for name in ("m0", "m1", "m2"):
        bus.add_master(name)
    bus.add_slave(base=0x0000, size=0x0100, name="s0")
    with pytest.raises(AxiConfigError):
        bus.build()


def test_crossbar_rejects_stream_variant():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="stream",
        interconnect=AxiCrossbar(),
    )
    bus.add_master("src")
    bus.add_slave(name="snk")
    with pytest.raises(AxiConfigError):
        bus.build()
