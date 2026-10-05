"""Shared-bus Wishbone demo: two BFM masters reach two CSR slaves.

Run with::

    python examples/wishbone_shared_bus.py
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.wishbone import CSRMap, SharedBus, Wishbone, WishboneBFM


@block
def shared_bus_demo(verbose=False):
    clk = Signal(bool(0))
    rst = Signal(bool(0))

    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, interconnect=SharedBus()
    )
    m0 = bus.add_master("m0")
    m1 = bus.add_master("m1")
    s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")
    s1 = bus.add_slave(base=0x1000, size=0x0100, name="s1")

    csr0 = CSRMap(width=32)
    csr0.add_ro(0x04, "ID", init=0xAAAA)
    csr1 = CSRMap(width=32)
    csr1.add_ro(0x04, "ID", init=0xBBBB)
    peri0 = csr0.build(s0)
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
        if verbose:
            print("m0 -> s0.ID = %#x" % bfm0.last_data)
        assert bfm0.last_data == 0xAAAA

    @instance
    def driver1():
        while rst:
            yield clk.posedge
        yield bfm1.read(0x1004)
        if verbose:
            print("m1 -> s1.ID = %#x" % bfm1.last_data)
        assert bfm1.last_data == 0xBBBB

    @instance
    def stopper():
        yield delay(20000)
        raise StopSimulation

    return clkgen, glue, peri0, peri1, do_reset, driver0, driver1, stopper


if __name__ == "__main__":
    shared_bus_demo(verbose=True).run_sim()
