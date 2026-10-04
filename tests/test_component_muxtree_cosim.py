"""Verilog cosimulation smoke test for ``MuxTree`` (Option A).

The same ``_bench`` used by the behavioural test drives either the Python block
or the converted Verilog RTL through ``Cosimulation``; both must agree.  A
subset of the policy matrix is cosimulated.
"""

import pytest
from test_component_muxtree_select import _python_device, _run, _vectors


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name)

    return _make


_COSIM_CASES = [
    (8, 5, "const", 0xAB, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 5, "lastinput", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 5, "alias", 0, 1, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 5, "wrap", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 8, "lastinput", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]),
    (8, 2, "lastinput", 0, 0, [0x11, 0x22]),  # power of two
    (8, 1, "lastinput", 0, 0, [0x5A]),  # n == 1, no select
]


@pytest.mark.parametrize("width,n,policy,default_value,alias,values", _COSIM_CASES)
def test_muxtree_cosim_matches_python(
    width, n, policy, default_value, alias, values, hdl_cosim
):
    vectors = _vectors(n, values)
    python = _run(_python_device, width, n, policy, default_value, alias, vectors)
    cosim = _run(
        _cosim_device(hdl_cosim, f"muxtree_{width}_{n}_{policy}"),
        width,
        n,
        policy,
        default_value,
        alias,
        vectors,
    )
    assert cosim == python
