"""AXI4 full demo: a BFM master drives an INCR burst to a memory slave.

Run with::

    python examples/axi_full_burst.py
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import (
    Axi,
    AxiBFM,
    AxiPointToPoint,
    axi_full_slave,
)


@block
def axi_full_burst_demo(verbose=False):
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")

    mem = axi_full_slave(s)
    bfm = AxiBFM(m, timeout=400)
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

        payload = [0x1111, 0x2222, 0x3333]
        yield bfm.write(0x00, payload)
        yield bfm.read(0x00, len(payload))
        if verbose:
            print("read back", [hex(value) for value in bfm.last_data])
        assert bfm.last_data == payload

        raise StopSimulation

    return clkgen, glue, mem, stim


if __name__ == "__main__":
    axi_full_burst_demo(verbose=True).run_sim()
