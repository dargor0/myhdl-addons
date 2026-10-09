"""Verilog cosimulation smoke test for ``FetchUnit`` (Option A)."""

import pytest
from test_riscv_fetch import _program, _python_device, _reference, _run

from myhdl_addons.riscv import FetchUnit


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        # power-on values make the converted registers match the Python model
        # from time 0 (the front-end has several internal state registers).
        return hdl_cosim(comp.hdl(ports), ports, name, initial_values=True)

    return _make


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_cosim_matches_python(depth, hdl_cosim):
    parcels = _program()
    expected = _reference(parcels, 0, 8)
    python = _run(_python_device, FetchUnit(fetch_buffer=depth), parcels, 8, latency=2)
    cosim = _run(
        _cosim_device(hdl_cosim, f"fetch_cosim_{depth}"),
        FetchUnit(fetch_buffer=depth),
        parcels,
        8,
        latency=2,
    )
    assert python == expected
    assert cosim == python


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_cosim_flush(depth, hdl_cosim):
    parcels = _program()
    python = _run(
        _python_device,
        FetchUnit(fetch_buffer=depth),
        parcels,
        6,
        split=3,
        redirect=0x0A,
    )
    cosim = _run(
        _cosim_device(hdl_cosim, f"fetch_cosim_flush_{depth}"),
        FetchUnit(fetch_buffer=depth),
        parcels,
        6,
        split=3,
        redirect=0x0A,
    )
    assert cosim == python
