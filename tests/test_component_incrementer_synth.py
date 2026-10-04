"""Yosys synthesizability smoke test for ``Incrementer`` (S1)."""

import pytest

from myhdl_addons.components import Incrementer


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8},
        {"width": 8, "steps": (2, 4, -2, -4), "carry": True},
        {"width": 8, "steps": (1,), "wrap_mode": "saturate", "carry": True},
        {"width": 8, "steps": (3, 4, 5), "carry": True},  # non-power-of-two
        {"width": 8, "load_enable": False},
        {"width": 8, "steps": (1,), "registered": 1},
    ],
)
def test_incrementer_synthesizes(kwargs, hdl_synth):
    comp = Incrementer(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "incrementer_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
