"""Basic full-mesh AXI4-Lite crossbar (AX-FR-060)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import (
    Axi,
    AxiCrossbar,
    AxiLiteBFM,
    AxiLiteCSR,
    AxiStatus,
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
        variant="lite",
        interconnect=AxiCrossbar(),
    )
    m0 = bus.add_master("m0")
    m1 = bus.add_master("m1")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    s1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    csr0 = AxiLiteCSR(width=32)
    csr0.add_write(0x00, "REG")
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    peri0 = csr0.build(s0)

    csr1 = AxiLiteCSR(width=32)
    csr1.add_write(0x00, "REG")
    csr1.add_ro(0x04, "ID", init=0xBBBB)
    peri1 = csr1.build(s1)

    bfm0 = AxiLiteBFM(m0, timeout=200)
    bfm1 = AxiLiteBFM(m1, timeout=200)
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
        yield bfm0.read(0x0004)
        assert bfm0.last_data == 0xAAAA, hex(bfm0.last_data)
        yield bfm0.write(0x0000, 0x1111)
        yield bfm0.read(0x0000)
        assert bfm0.last_data == 0x1111, hex(bfm0.last_data)

    @instance
    def driver1():
        while not aresetn:
            yield aclk.posedge
        yield bfm1.read(0x1004)
        assert bfm1.last_data == 0xBBBB, hex(bfm1.last_data)
        yield bfm1.write(0x1000, 0x2222)
        yield bfm1.read(0x1000)
        assert bfm1.last_data == 0x2222, hex(bfm1.last_data)

    @instance
    def stopper():
        yield delay(20000)
        raise StopSimulation

    return clkgen, glue, peri0, peri1, do_reset, driver0, driver1, stopper


def test_axi_lite_crossbar_concurrent():
    _tb().run_sim()


@block
def _dec_tb():
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="lite",
        interconnect=AxiCrossbar(),
    )
    m0 = bus.add_master("m0")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")

    csr0 = AxiLiteCSR(width=32)
    csr0.add_write(0x00, "REG")
    peri0 = csr0.build(s0)

    bfm0 = AxiLiteBFM(m0, timeout=50)
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

        yield bfm0.read(0x8000)
        assert bfm0.last_resp is AxiStatus.DECERR
        yield bfm0.write(0x8000, 0x1234)
        assert bfm0.last_resp is AxiStatus.DECERR

        raise StopSimulation

    return clkgen, glue, peri0, stim


def test_axi_lite_crossbar_decoder_error():
    _dec_tb().run_sim()
