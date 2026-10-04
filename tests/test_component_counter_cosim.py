"""Verilog cosimulation smoke test for ``Counter`` (Option A).

The same ``_counter_tb`` used by the behavioural test drives either the Python
block or the converted Verilog RTL; both must agree.
"""

import pytest

from test_component_counter_count import _run


def _cosim_device(hdl_cosim, name):
    def _make(counter, ports):
        return hdl_cosim(counter.hdl(ports), ports, name)

    return _make


_CASES = [
    ({"width": 4, "max": 3}, [{"en": 1}] * 5),
    (
        {"width": 4, "steps": (1, 2), "max": 15},
        [
            {"en": 1, "step_sel": 0},
            {"en": 1, "step_sel": 1},
            {"en": 1, "step_sel": 0},
        ],
    ),
    (
        {"width": 4, "max": 15, "load_enable": True},
        [{"en": 0, "load": 1, "load_value": 7}, {"en": 1, "load": 0}],
    ),
    ({"width": 4, "max": 15, "prescaler": 2}, [{"en": 1}] * 4),
    ({"width": 4, "max": 3, "wrap_mode": "saturate"}, [{"en": 1}] * 5),
    (
        {"width": 4, "max": 15, "steps": (1, 2, 3)},
        [
            {"en": 1, "step_sel": 0},
            {"en": 1, "step_sel": 3},  # out-of-range holds count
            {"en": 1, "step_sel": 1},
        ],
    ),
    ({"width": 4, "max": 15, "steps": (-1,)}, [{"en": 1}] * 3),
]


@pytest.mark.parametrize("config,drives", _CASES)
def test_counter_cosim_matches_python(config, drives, hdl_cosim):
    python = _run(config, drives)
    cosim = _run(config, drives, make_device=_cosim_device(hdl_cosim, "cnt_cosim"))
    assert cosim == python
