"""Verilog cosimulation smoke test for ``Incrementer`` (Option A).

The same ``_inc_tb`` used by the behavioural test drives either the Python
block or the converted Verilog RTL; both must agree.
"""

import pytest
from test_component_incrementer_steps import _run


def _cosim_device(hdl_cosim, name):
    def _make(inc, ports):
        return hdl_cosim(inc.hdl(ports), ports, name)

    return _make


_CASES = [
    {"a": 5, "steps": (2, 4, -2, -4), "sel": 0},
    {"a": 5, "steps": (2, 4, -2, -4), "sel": 3},  # power-of-two steps
    {"a": 0xFF, "steps": (1,), "wrap_mode": "saturate", "carry": True},
    {"a": 0xFF, "steps": (1,), "wrap_mode": "wrap", "carry": True},
    {"a": 0, "steps": (-1,), "wrap_mode": "wrap"},
    {"a": 5, "load": 1, "load_value": 0xAB},
    {"a": 5, "en": 0},
    {"a": 5, "steps": (3, 4, 5), "sel": 3},  # out-of-range holds a
    {"a": 5, "steps": (1,), "load_enable": False},
]


@pytest.mark.parametrize("kwargs", _CASES)
def test_incrementer_cosim_matches_python(kwargs, hdl_cosim):
    python = _run(**kwargs)
    cosim = _run(make_device=_cosim_device(hdl_cosim, "inc_cosim"), **kwargs)
    assert cosim == python
