"""AXI4-Lite master core (AX-FR-040)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import Axi, AxiLiteCSR, AxiPointToPoint, axi_lite_master


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
    peri = csr.build(s)

    start = Signal(bool(0))
    write = Signal(bool(0))
    addr = Signal(intbv(0)[16:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    busy = Signal(bool(0))
    done = Signal(bool(0))
    rdata = Signal(intbv(0)[32:])
    resp = Signal(intbv(0)[2:])

    master = axi_lite_master(
        m, start, write, addr, wdata, wstrb, busy, done, rdata, resp
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

        # write CTRL = 0x1234
        addr.next = 0x00
        write.next = 1
        wdata.next = 0x1234
        wstrb.next = 0xF
        start.next = 1
        yield aclk.posedge
        start.next = 0
        while not done:
            yield aclk.posedge
        assert int(resp) == 0
        yield aclk.posedge

        # read CTRL
        addr.next = 0x00
        write.next = 0
        start.next = 1
        yield aclk.posedge
        start.next = 0
        while not done:
            yield aclk.posedge
        assert int(rdata) == 0x1234, hex(int(rdata))
        yield aclk.posedge

        # read ID
        addr.next = 0x04
        start.next = 1
        yield aclk.posedge
        start.next = 0
        while not done:
            yield aclk.posedge
        assert int(rdata) == 0xC0DE, hex(int(rdata))

        raise StopSimulation

    return clkgen, glue, peri, master, stim


def test_axi_lite_master_core():
    _tb().run_sim()
