"""Shared-bus interconnect simulation: 2 masters, 2 slaves, concurrency."""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.wishbone import CSRMap, SharedBus, Wishbone, WishboneBFM


@block
def _shared_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))

    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=SharedBus()
    )
    m0 = bus.add_master("m0")
    m1 = bus.add_master("m1")
    s0 = bus.add_slave(base=0x0000, size=0x100, name="s0")
    s1 = bus.add_slave(base=0x1000, size=0x100, name="s1")

    csr0 = CSRMap(width=32)
    csr0.add_write(0x00, "REG", init=0)
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    peri0 = csr0.build(s0)

    csr1 = CSRMap(width=32)
    csr1.add_write(0x00, "REG", init=0)
    csr1.add_ro(0x04, "ID", init=0xBBBB)
    peri1 = csr1.build(s1)

    bfm0 = WishboneBFM(m0, timeout=200)
    bfm1 = WishboneBFM(m1, timeout=200)
    glue = bus.build()

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def do_reset():
        rst.next = 1
        yield clk.posedge
        yield clk.posedge
        rst.next = 0

    @instance
    def driver0():
        while rst:
            yield clk.posedge
        yield bfm0.read(0x0004)
        assert bfm0.last_data == 0xAAAA, hex(bfm0.last_data)
        yield bfm0.write(0x0000, 0x1234)
        yield bfm0.read(0x0000)
        assert bfm0.last_data == 0x1234, hex(bfm0.last_data)

    @instance
    def driver1():
        while rst:
            yield clk.posedge
        yield bfm1.read(0x1004)
        assert bfm1.last_data == 0xBBBB, hex(bfm1.last_data)
        yield bfm1.write(0x1000, 0x5678)
        yield bfm1.read(0x1000)
        assert bfm1.last_data == 0x5678, hex(bfm1.last_data)

    @instance
    def stopper():
        yield delay(20000)
        raise StopSimulation

    return clkgen, glue, peri0, peri1, do_reset, driver0, driver1, stopper


def test_shared_bus_two_masters_two_slaves():
    _shared_tb().run_sim()
