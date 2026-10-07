"""Verilog cosimulation smoke test for the common address decoder (Option A).

The decoder's public API takes a list of select signals, so the lists are kept
internal and tied to packed ports (see the conversion test); the same bench
drives either the Python block or the converted Verilog RTL.
"""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv
from test_bus_common_addrmap_conversion import _addrdec_top

from myhdl_addons.common.views import SignalView


def _ports():
    return SignalView(
        adr=Signal(intbv(0)[8:]),
        sel0=Signal(bool(0)),
        sel1=Signal(bool(0)),
        sel2=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _addrdec_top(ports.adr, ports.sel0, ports.sel1, ports.sel2)


@block
def _bench(make_dut, ports, vectors, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.adr.next = 0xFF  # prime (differs from the first vector, 0x00)
        yield delay(1)
        for addr in vectors:
            ports.adr.next = addr
            yield delay(1)
            results.append((int(ports.sel0), int(ports.sel1), int(ports.sel2)))
        raise StopSimulation

    return dut, stim


_VECTORS = [0x00, 0x05, 0x1F, 0x20, 0x2F, 0x30, 0x4F, 0x50, 0xFF]


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, _VECTORS, results).run_sim()
    return results


def test_address_decoder_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "bus_addrdec_cosim")

    assert _run(cosim) == _run(_dut)
