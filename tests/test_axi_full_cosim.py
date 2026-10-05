"""Verilog cosimulation smoke test for the AXI4 full master + memory slave (Option A).

The same clocked bench drives either the Python instances or the converted
Verilog RTL bound to an equivalent ``SignalView``; the burst write/read data and
status must match exactly.
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv
from test_axi_rtl_conversion import _full_top

from myhdl_addons.common.views import SignalView


def _ports():
    return SignalView(
        aclk=Signal(bool(0)),
        aresetn=Signal(bool(0)),
        start=Signal(bool(0)),
        write=Signal(bool(0)),
        addr=Signal(intbv(0)[16:]),
        length=Signal(intbv(0)[8:]),
        wdata=Signal(intbv(0)[32:]),
        wstrb=Signal(intbv(0)[4:]),
        wvalid=Signal(bool(0)),
        wready=Signal(bool(0)),
        rdata=Signal(intbv(0)[32:]),
        rvalid=Signal(bool(0)),
        rready=Signal(bool(0)),
        busy=Signal(bool(0)),
        done=Signal(bool(0)),
        observe=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _full_top(
        ports.aclk,
        ports.aresetn,
        ports.start,
        ports.write,
        ports.addr,
        ports.length,
        ports.wdata,
        ports.wstrb,
        ports.wvalid,
        ports.wready,
        ports.rdata,
        ports.rvalid,
        ports.rready,
        ports.busy,
        ports.done,
        ports.observe,
    )


@block
def _bench(make_dut, ports, results):
    dut = make_dut(ports)

    @always(delay(5))
    def clkgen():
        ports.aclk.next = not ports.aclk

    @instance
    def stim():
        ports.aresetn.next = 0
        yield ports.aclk.posedge
        yield ports.aclk.posedge
        ports.aresetn.next = 1

        # write a 3-beat burst at 0x00
        ports.addr.next = 0x00
        ports.length.next = 3
        ports.write.next = 1
        ports.start.next = 1
        yield ports.aclk.posedge
        ports.start.next = 0
        for value in (0x1111, 0x2222, 0x3333):
            ports.wdata.next = value
            ports.wstrb.next = 0xF
            ports.wvalid.next = 1
            yield ports.aclk.posedge
            while not ports.wready:
                yield ports.aclk.posedge
            ports.wvalid.next = 0
            yield ports.aclk.posedge
        while not ports.done:
            yield ports.aclk.posedge
        yield delay(1)
        results.append(("wr", int(ports.busy), int(ports.done)))
        yield ports.aclk.posedge

        # read back with single-beat reads
        for offset in (0x00, 0x04, 0x08):
            ports.rready.next = 1
            ports.addr.next = offset
            ports.length.next = 1
            ports.write.next = 0
            ports.start.next = 1
            yield ports.aclk.posedge
            ports.start.next = 0
            while not ports.rvalid:
                yield ports.aclk.posedge
            yield delay(1)
            results.append(("rd", offset, int(ports.rdata), int(ports.rvalid)))
            yield ports.aclk.posedge
            ports.rready.next = 0
            yield ports.aclk.posedge
        raise StopSimulation

    return dut, clkgen, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_axi_full_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "axi_full_cosim")

    assert _run(cosim) == _run(_dut)
