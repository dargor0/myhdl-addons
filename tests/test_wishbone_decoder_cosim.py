"""Verilog cosimulation smoke test for the Wishbone address decoder (Option A).

The same bench drives either the Python block or the converted Verilog RTL
bound to an equivalent ``SignalView``; both must agree.
"""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv

from myhdl_addons.common.views import SignalView
from test_wishbone_decoder_conversion import _dec_top


def _ports():
    return SignalView(
        adr=Signal(intbv(0)[16:]),
        sel0=Signal(bool(0)),
        sel1=Signal(bool(0)),
        sel2=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _dec_top(ports.adr, ports.sel0, ports.sel1, ports.sel2)


@block
def _bench(make_dut, ports, vectors, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.adr.next = 0xFFFF  # kick the converted logic
        yield delay(1)
        for adr in vectors:
            ports.adr.next = adr
            yield delay(1)
            results.append((int(ports.sel0), int(ports.sel1), int(ports.sel2)))
        raise StopSimulation

    return dut, stim


_VECTORS = [0x0000, 0x00FF, 0x0100, 0x0FFF, 0x1000, 0x10FF, 0x2000, 0x2FFF, 0x3000]


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, _VECTORS, results).run_sim()
    return results


def test_wishbone_decoder_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "wb_addrdec_cosim")

    assert _run(cosim) == _run(_dut)
