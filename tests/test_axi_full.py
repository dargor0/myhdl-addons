"""AXI4 full memory slave + INCR bursts (AX-FR-030..037)."""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import (
    Axi,
    AxiBFM,
    AxiPointToPoint,
    AxiStatus,
    axi_full_slave,
    axi_master,
)


@block
def _tb():
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
    bfm = AxiBFM(m, timeout=200)
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

        yield bfm.write(0x00, [0x1111, 0x2222, 0x3333])
        assert bfm.last_resp is AxiStatus.OKAY

        yield bfm.read(0x00, 3)
        assert bfm.last_data == [0x1111, 0x2222, 0x3333], bfm.last_data

        # single-beat write then read at an offset
        yield bfm.write(0x10, [0xABCD])
        yield bfm.read(0x10, 1)
        assert bfm.last_data == [0xABCD], bfm.last_data

        raise StopSimulation

    return clkgen, glue, mem, stim


def test_axi_full_memory_slave_bursts():
    _tb().run_sim()


@block
def _master_tb():
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

    start = Signal(bool(0))
    write = Signal(bool(0))
    addr = Signal(intbv(0)[16:])
    length = Signal(intbv(0)[8:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    wvalid = Signal(bool(0))
    wready = Signal(bool(0))
    rdata = Signal(intbv(0)[32:])
    rvalid = Signal(bool(0))
    rready = Signal(bool(0))
    busy = Signal(bool(0))
    done = Signal(bool(0))

    master = axi_master(
        m,
        start,
        write,
        addr,
        length,
        wdata,
        wstrb,
        wvalid,
        wready,
        rdata,
        rvalid,
        rready,
        busy,
        done,
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

        # write a 3-beat burst
        addr.next = 0x00
        length.next = 3
        write.next = 1
        start.next = 1
        yield aclk.posedge
        start.next = 0
        for value in (0x1111, 0x2222, 0x3333):
            wdata.next = value
            wstrb.next = 0xF
            wvalid.next = 1
            yield aclk.posedge
            while not wready:
                yield aclk.posedge
            wvalid.next = 0
            yield aclk.posedge
        while not done:
            yield aclk.posedge

        # read back with single-beat reads
        got = []
        for offset, expected in [(0x00, 0x1111), (0x04, 0x2222), (0x08, 0x3333)]:
            rready.next = 1
            addr.next = offset
            length.next = 1
            write.next = 0
            start.next = 1
            yield aclk.posedge
            start.next = 0
            while not rvalid:
                yield aclk.posedge
            got.append(int(rdata))
            yield aclk.posedge
            rready.next = 0
            yield aclk.posedge
        assert got == [0x1111, 0x2222, 0x3333], got

        raise StopSimulation

    return clkgen, glue, mem, master, stim


def test_axi_full_master_core():
    _master_tb().run_sim()
