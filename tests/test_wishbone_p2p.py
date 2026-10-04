"""End-to-end point-to-point simulation: BFM (master) <-> CSR (slave)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.wishbone import CSRMap, PointToPoint, Wishbone, WishboneBFM


@block
def _tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))

    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=PointToPoint()
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="csr")

    csr = CSRMap(width=32)
    csr.add_write(0x00, "CTRL")
    csr.add_ro(0x04, "ID", init=0xC0DE)
    peri = csr.build(s)

    bfm = WishboneBFM(m)
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
        yield bfm.read(0x00)
        assert bfm.last_data == 0x1234, hex(bfm.last_data)

        yield bfm.read(0x04)
        assert bfm.last_data == 0xC0DE, hex(bfm.last_data)

        # write then read-back through the BFM's RMW helper
        yield bfm.rmw(0x00, 0x0000_00FF, 0xABCD)
        yield bfm.read(0x00)
        assert bfm.last_data == 0x12CD, hex(bfm.last_data)

        raise StopSimulation

    return clkgen, glue, peri, stim


def test_p2p_csr():
    _tb().run_sim()
