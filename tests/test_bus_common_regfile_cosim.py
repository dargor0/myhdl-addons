"""Verilog cosimulation smoke test for the common register/CSR engine (Option A)."""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv
from test_bus_common_regfile_conversion import _csr_top

from myhdl_addons.common.views import SignalView


def _ports():
    return SignalView(
        clk=Signal(bool(0)),
        rst=Signal(bool(0)),
        req=Signal(bool(0)),
        we=Signal(bool(0)),
        addr=Signal(intbv(0)[8:]),
        wdata=Signal(intbv(0)[32:]),
        wstrb=Signal(intbv(0)[4:]),
        rdata=Signal(intbv(0)[32:]),
        ack=Signal(bool(0)),
        rw_out=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _csr_top(
        ports.clk,
        ports.rst,
        ports.req,
        ports.we,
        ports.addr,
        ports.wdata,
        ports.wstrb,
        ports.rdata,
        ports.ack,
        ports.rw_out,
    )


def _snap(ports):
    return (int(ports.rdata), int(ports.ack), int(ports.rw_out))


@block
def _bench(make_dut, ports, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.rst.next = 1
        ports.clk.next = 1
        yield delay(1)
        results.append(_snap(ports))
        ports.clk.next = 0
        yield delay(1)
        ports.rst.next = 0

        # write ctrl = 0x1234
        ports.addr.next = 0x00
        ports.wdata.next = 0x1234
        ports.wstrb.next = 0xF
        ports.req.next = 1
        ports.we.next = 1
        yield delay(1)
        results.append(_snap(ports))
        ports.clk.next = 1
        yield delay(1)
        ports.clk.next = 0
        yield delay(1)
        results.append(_snap(ports))

        # partial write (low two bytes)
        ports.wdata.next = 0xFFFFFFFF
        ports.wstrb.next = 0x3
        ports.clk.next = 1
        yield delay(1)
        ports.clk.next = 0
        yield delay(1)
        results.append(_snap(ports))

        # write-1-to-clear
        ports.addr.next = 0x0C
        ports.wdata.next = 0x0F
        ports.wstrb.next = 0xF
        ports.clk.next = 1
        yield delay(1)
        ports.clk.next = 0
        yield delay(1)
        results.append(_snap(ports))

        # reads
        ports.we.next = 0
        ports.addr.next = 0x00
        yield delay(1)
        results.append(_snap(ports))
        ports.addr.next = 0x04
        yield delay(1)
        results.append(_snap(ports))
        ports.addr.next = 0x40
        yield delay(1)
        results.append(_snap(ports))
        ports.req.next = 0
        yield delay(1)
        results.append(_snap(ports))
        raise StopSimulation

    return dut, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_register_engine_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "bus_csr_cosim")

    assert _run(cosim) == _run(_dut)
