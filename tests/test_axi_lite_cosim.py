"""Verilog cosimulation smoke test for the AXI4-Lite master + CSR (Option A).

The same clocked bench drives either the Python instances or the converted
Verilog RTL bound to an equivalent ``SignalView``; the write/read results and
response codes must match exactly.
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.common.views import SignalView
from test_axi_rtl_conversion import _lite_top


def _ports():
    return SignalView(
        aclk=Signal(bool(0)),
        aresetn=Signal(bool(0)),
        start=Signal(bool(0)),
        write=Signal(bool(0)),
        addr=Signal(intbv(0)[16:]),
        wdata=Signal(intbv(0)[32:]),
        wstrb=Signal(intbv(0)[4:]),
        busy=Signal(bool(0)),
        done=Signal(bool(0)),
        rdata=Signal(intbv(0)[32:]),
        resp=Signal(intbv(0)[2:]),
        status_in=Signal(intbv(0)[32:]),
        strobes=Signal(bool(0)),
        observe=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _lite_top(
        ports.aclk,
        ports.aresetn,
        ports.start,
        ports.write,
        ports.addr,
        ports.wdata,
        ports.wstrb,
        ports.busy,
        ports.done,
        ports.rdata,
        ports.resp,
        ports.status_in,
        ports.strobes,
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
        ports.status_in.next = 0x55
        yield ports.aclk.posedge
        yield ports.aclk.posedge
        ports.aresetn.next = 1

        # write CTRL = 0x1234
        ports.addr.next = 0x00
        ports.write.next = 1
        ports.wdata.next = 0x1234
        ports.wstrb.next = 0xF
        ports.start.next = 1
        yield ports.aclk.posedge
        ports.start.next = 0
        while not ports.done:
            yield ports.aclk.posedge
        yield delay(1)
        results.append((int(ports.busy), int(ports.resp), int(ports.rdata)))
        yield ports.aclk.posedge

        # read CTRL
        ports.addr.next = 0x00
        ports.write.next = 0
        ports.start.next = 1
        yield ports.aclk.posedge
        ports.start.next = 0
        while not ports.done:
            yield ports.aclk.posedge
        yield delay(1)
        results.append((int(ports.busy), int(ports.resp), int(ports.rdata)))
        yield ports.aclk.posedge

        # read ID
        ports.addr.next = 0x04
        ports.start.next = 1
        yield ports.aclk.posedge
        ports.start.next = 0
        while not ports.done:
            yield ports.aclk.posedge
        yield delay(1)
        results.append((int(ports.busy), int(ports.resp), int(ports.rdata)))
        yield ports.aclk.posedge

        # read STATUS -> status_in
        ports.addr.next = 0x08
        ports.start.next = 1
        yield ports.aclk.posedge
        ports.start.next = 0
        while not ports.done:
            yield ports.aclk.posedge
        yield delay(1)
        results.append((int(ports.busy), int(ports.resp), int(ports.rdata)))
        raise StopSimulation

    return dut, clkgen, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_axi_lite_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "axi_lite_cosim")

    assert _run(cosim) == _run(_dut)
