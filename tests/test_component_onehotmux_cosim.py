"""Verilog cosimulation smoke test for ``OneHotMux`` (Option A).

The same ``_onehot_bench`` used by the behavioural test drives either the
Python block or the converted Verilog RTL; both must agree.
"""

import pytest
from test_component_onehotmux_select import _python_device, _run


def _cosim_device(hdl_cosim, name):
    def _make(mux, ports):
        return hdl_cosim(mux.hdl(ports), ports, name)

    return _make


_COSIM_CASES = [
    (0b001, (0x11, 0x22, 0x33), {}),
    (0b011, (0x01, 0x02, 0x00), {}),  # multi-hot OR
    (0b000, (0x11, 0x22, 0x33), {"valid": True}),
    (0b110, (0x11, 0x22, 0x33), {"valid": True}),
    (0b011, (0x11, 0x22, 0x33), {"valid": True, "strict": True}),
    (0b10, (0x00, 0xFF), {}),  # n == 2
]


@pytest.mark.parametrize("sel,values,kwargs", _COSIM_CASES)
def test_onehotmux_cosim_matches_python(sel, values, kwargs, hdl_cosim):
    python = _run(_python_device, sel, values, **kwargs)
    cosim = _run(_cosim_device(hdl_cosim, "onehot_cosim"), sel, values, **kwargs)
    assert cosim == python
