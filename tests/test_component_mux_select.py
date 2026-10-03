"""Binary-select mux semantics (``IC-FR-060..064``)."""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import Mux


@block
def _mux_tb(results, width, n, values, sel, default_value=0, valid=False):
    mux = Mux(width=width, n=n, default_value=default_value, valid=valid)
    ports = mux.ports()
    dut = mux.hdl(ports)
    valid_sig = ports.signals.get("valid")

    @instance
    def stim():
        for i, value in enumerate(values):
            ports.inputs[i].next = value
        ports.sel.next = sel
        yield delay(1)
        results.append(
            (int(ports.y), int(valid_sig) if valid_sig is not None else None)
        )
        raise StopSimulation

    return dut, stim


def _run(sel, values, width=8, **kwargs):
    results = []
    _mux_tb(results, width, len(values), values, sel, **kwargs).run_sim()
    return results[0]


@pytest.mark.parametrize("values", [(0x00, 0x7F, 0x80, 0xFF)])
def test_selects_each_input(values):
    for sel, expect in enumerate(values):
        assert _run(sel, values) == (expect, None)


def test_out_of_range_uses_default():
    y, _ = _run(3, (0x11, 0x22, 0x33), default_value=0xEE)
    assert y == 0xEE


def test_valid_output():
    assert _run(2, (0x11, 0x22, 0x33), valid=True) == (0x33, 1)
    assert _run(3, (0x11, 0x22, 0x33), valid=True) == (0, 0)


def test_single_input():
    assert _run(0, (0x5A,)) == (0x5A, None)
    assert _run(1, (0x5A,), default_value=0x0F) == (0x0F, None)


def test_sel_width():
    assert Mux(width=8, n=1).sel_bits == 1
    assert Mux(width=8, n=3).sel_bits == 2
    assert Mux(width=8, n=5).sel_bits == 3
