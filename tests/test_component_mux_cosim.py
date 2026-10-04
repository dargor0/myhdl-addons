"""Verilog cosimulation smoke test for ``Mux`` (Option A).

The same ``_mux_bench`` used by the behavioural test drives either the Python
block or the converted Verilog RTL; both must agree.
"""

import pytest
from test_component_mux_select import _python_device, _run


def _cosim_device(hdl_cosim, name):
    def _make(mux, ports):
        return hdl_cosim(mux.hdl(ports), ports, name)

    return _make


_COSIM_CASES = [
    (2, (0x00, 0x7F, 0x80, 0xFF), {}),
    (3, (0x11, 0x22, 0x33), {"default_value": 0xEE}),
    (2, (0x11, 0x22, 0x33), {"valid": True}),
    (3, (0x11, 0x22, 0x33), {"valid": True}),  # out-of-range -> valid=0
    (0, (0x5A,), {}),  # n == 1
    (1, (0x5A,), {"default_value": 0x0F}),
    (1, (0x11, 0x22, 0x33, 0x44), {"valid": True}),  # power-of-two n
]


@pytest.mark.parametrize("sel,values,kwargs", _COSIM_CASES)
def test_mux_cosim_matches_python(sel, values, kwargs, hdl_cosim):
    python = _run(_python_device, sel, values, **kwargs)
    cosim = _run(_cosim_device(hdl_cosim, "mux_cosim"), sel, values, **kwargs)
    assert cosim == python
