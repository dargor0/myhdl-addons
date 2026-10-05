"""Point-to-point Wishbone demo: a BFM master drives a CSR peripheral.

Run with::

    python examples/wishbone_p2p_csr.py
"""

from myhdl import (block, instance, always, delay, Signal, intbv,
                   StopSimulation)

from myhdl_addons.wishbone import Wishbone, PointToPoint, CSRMap, WishboneBFM


@block
def p2p_demo(verbose=False):
    clk = Signal(bool(0))
    rst = Signal(bool(0))

    # one bus, one master, one peripheral
    bus = Wishbone(clk, rst, data_width=32, adr_width=16, gran=8,
                   interconnect=PointToPoint())
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="csr")

    csr = CSRMap(width=32)
    csr.add_write(0x00, "CTRL")
    csr.add_ro(0x04, "ID", init=0xB005)
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

        yield bfm.write(0x00, 0xDEAD_BEEF)
        yield bfm.read(0x00)
        if verbose:
            print("CTRL = %#x" % bfm.last_data)

        yield bfm.read(0x04)
        if verbose:
            print("ID   = %#x" % bfm.last_data)

        raise StopSimulation

    return clkgen, glue, peri, stim


if __name__ == "__main__":
    p2p_demo(verbose=True).run_sim()
