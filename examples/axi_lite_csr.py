"""AXI4-Lite demo: a BFM master drives an AXI-Lite CSR peripheral (AX-FR-121).

Run with::

    python examples/axi_lite_csr.py
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import Axi, AxiLiteBFM, AxiLiteCSR, AxiPointToPoint


@block
def axi_lite_csr_demo(verbose=False):
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
    csr.add_ro(0x04, "ID", init=0x0A11)
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
    axi_lite_csr_demo(verbose=True).run_sim()
