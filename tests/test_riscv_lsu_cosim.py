"""Verilog cosimulation smoke test for ``LoadStoreUnit`` (Option A)."""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv
from test_riscv_lsu import _VECTORS

from myhdl_addons.common.views import SignalView
from myhdl_addons.riscv import LoadStoreUnit


def _ports():
    return SignalView(
        addr=Signal(intbv(0)[32:]),
        wdata=Signal(intbv(0)[32:]),
        rdata=Signal(intbv(0)[32:]),
        size=Signal(intbv(0)[2:]),
        zero_extend=Signal(bool(0)),
        load_data=Signal(intbv(0)[32:]),
        store_data=Signal(intbv(0)[32:]),
        wstrb=Signal(intbv(0)[4:]),
        misaligned=Signal(bool(0)),
    )


@block
def _dut(ports):
    return LoadStoreUnit().hdl(ports)


@block
def _bench(make_dut, ports, vectors, results):
    dut = make_dut(ports)

    @instance
    def stim():
        # prime with a value differing from the first vector
        ports.addr.next = 0xFFFFFFFF
        ports.wdata.next = 0xFFFFFFFF
        ports.rdata.next = 0xFFFFFFFF
        ports.size.next = 2
        ports.zero_extend.next = 1
        yield delay(1)
        for addr, wdata, rdata, size, zero_extend in vectors:
            ports.addr.next = addr
            ports.wdata.next = wdata
            ports.rdata.next = rdata
            ports.size.next = size
            ports.zero_extend.next = zero_extend
            yield delay(1)
            results.append(
                (
                    int(ports.load_data),
                    int(ports.store_data),
                    int(ports.wstrb),
                    int(ports.misaligned),
                )
            )
        raise StopSimulation

    return dut, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, _VECTORS, results).run_sim()
    return results


def test_lsu_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "lsu_cosim")

    assert _run(cosim) == _run(_dut)
