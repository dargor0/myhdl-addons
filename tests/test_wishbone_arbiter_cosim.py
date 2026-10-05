"""Verilog cosimulation smoke test for the Wishbone arbiter (Option A).

The ``req``/``grant`` lists are kept internal and tied to packed vector ports,
so the same bench drives either the Python block or the converted Verilog RTL.
"""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv
from test_wishbone_arbiter_conversion import _arb_top

from myhdl_addons.common.views import SignalView


def _ports():
    return SignalView(
        req_vec=Signal(intbv(0)[3:]),
        grant_vec=Signal(intbv(0)[3:]),
    )


@block
def _dut(ports):
    return _arb_top(ports.req_vec, ports.grant_vec)


@block
def _bench(make_dut, ports, vectors, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.req_vec.next = 0b111  # kick
        yield delay(1)
        for req in vectors:
            ports.req_vec.next = req
            yield delay(1)
            results.append(int(ports.grant_vec))
        raise StopSimulation

    return dut, stim


_VECTORS = [0b001, 0b010, 0b100, 0b011, 0b101, 0b110, 0b111, 0b000]


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, _VECTORS, results).run_sim()
    return results


def test_wishbone_arbiter_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "wb_arb_cosim")

    assert _run(cosim) == _run(_dut)
