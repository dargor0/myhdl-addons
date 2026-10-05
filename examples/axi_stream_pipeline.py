"""AXI4-Stream pipeline demo: a source sends a packet to a sink (AX-FR-121).

Run with::

    python examples/axi_stream_pipeline.py
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import Axi, AxiPointToPoint, axis_sink, axis_source


@block
def axi_stream_pipeline_demo(verbose=False):
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="stream",
        interconnect=AxiPointToPoint(),
    )
    src_port = bus.add_master("src")
    snk_port = bus.add_slave(name="snk")

    din = Signal(intbv(0)[32:])
    vin = Signal(bool(0))
    lin = Signal(bool(0))
    rdy = Signal(bool(0))
    dout = Signal(intbv(0)[32:])
    vout = Signal(bool(0))
    lout = Signal(bool(0))
    rin = Signal(bool(0))

    src = axis_source(src_port, din, vin, lin, rdy)
    snk = axis_sink(snk_port, rin, dout, vout, lout)
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

        packet = [0x10, 0x20, 0x30]
        received = []
        rin.next = 1
        for i, beat in enumerate(packet):
            din.next = beat
            vin.next = 1
            lin.next = 1 if i == len(packet) - 1 else 0
            while True:
                yield aclk.posedge
                if vout:
                    received.append(int(dout))
                    break
        vin.next = 0
        if verbose:
            print("received", [hex(value) for value in received])
        assert received == packet

        raise StopSimulation

    return clkgen, glue, src, snk, stim


if __name__ == "__main__":
    axi_stream_pipeline_demo(verbose=True).run_sim()
