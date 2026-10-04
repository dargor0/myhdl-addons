"""Yosys synthesizability smoke test for ``Counter`` (S1)."""

import pytest

from myhdl_addons.components import Counter


@pytest.mark.parametrize(
    "config",
    [
        {"width": 8},
        {"width": 8, "max": 100, "steps": (1, -1), "tick": True},
        {"width": 8, "steps": (1, 2, 3), "prescaler": 4},
        {"width": 8, "max": 10, "wrap_mode": "saturate", "load_enable": False},
    ],
)
def test_counter_synthesizes(config, hdl_synth):
    comp = Counter(**config)
    result = hdl_synth(comp.hdl(comp.ports()), "counter_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
