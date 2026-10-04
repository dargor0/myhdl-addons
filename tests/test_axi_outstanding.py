"""AXI outstanding reads with ID echo (AX-FR-022/033)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.axi import Axi, AxiBFM, AxiPointToPoint, axi_full_slave_oo


@block
def _tb(depth, requests, expected):
    aclk = Signal(bool(0))
    aresetn = Signal(bool(0))

    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        id_width=4,
        variant="full",
        interconnect=AxiPointToPoint(),
    )
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x0100, name="mem")

    mem = axi_full_slave_oo(s, depth=depth)
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

        # fill memory through the (single-outstanding) write path
        yield bfm.write(0x00, [0x11, 0x22, 0x33])
        yield bfm.write(0x10, [0xAA, 0xBB])

        yield bfm.read_outstanding(requests)
        assert bfm.last_outstanding == expected, bfm.last_outstanding

        raise StopSimulation

    return clkgen, glue, mem, stim


def test_outstanding_reads_grouped_by_id():
    _tb(
        depth=4,
        requests=[(0x00, 3, 0), (0x10, 2, 1), (0x04, 1, 2)],
        expected={0: [0x11, 0x22, 0x33], 1: [0xAA, 0xBB], 2: [0x22]},
    ).run_sim()


def test_outstanding_same_id_preserves_order():
    _tb(
        depth=4,
        requests=[(0x00, 2, 5), (0x10, 2, 5)],
        expected={5: [0x11, 0x22, 0xAA, 0xBB]},
    ).run_sim()


def test_outstanding_depth_clamped_minimum():
    _tb(
        depth=1,  # clamped to 2
        requests=[(0x00, 1, 0), (0x10, 1, 1)],
        expected={0: [0x11], 1: [0xAA]},
    ).run_sim()
