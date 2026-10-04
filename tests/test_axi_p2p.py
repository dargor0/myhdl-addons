"""End-to-end AXI4-Lite point-to-point: BFM (master) <-> CSR (slave)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import Axi, AxiLiteBFM, AxiLiteCSR, AxiPointToPoint


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
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="csr")

    csr = AxiLiteCSR(width=32)
    csr.add_write(0x00, "CTRL")
    csr.add_ro(0x04, "ID", init=0xC0DE)
    csr.add_read(0x08, "STATUS")
    peri = csr.build(s)

    bfm = AxiLiteBFM(m)
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

        yield bfm.write(0x00, 0x1234)
        yield bfm.read(0x00)
        assert bfm.last_data == 0x1234, hex(bfm.last_data)

        yield bfm.read(0x04)
        assert bfm.last_data == 0xC0DE, hex(bfm.last_data)

        yield bfm.rmw(0x00, 0x0000_00FF, 0xABCD)
        yield bfm.read(0x00)
        assert bfm.last_data == 0x12CD, hex(bfm.last_data)

        raise StopSimulation

    return clkgen, glue, peri, stim


def test_axi_lite_p2p_csr():
    _tb().run_sim()
