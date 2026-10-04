"""Yosys synthesizability smoke test for ``Mux`` (S1)."""

import pytest

from myhdl_addons.components import Mux


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "n": 3},
        {"width": 8, "n": 5, "default_value": 0xEE, "valid": True},
        {"width": 8, "n": 4, "registered": True, "en": True, "valid": True},
        {"width": 8, "n": 1, "valid": True},
    ],
)
def test_mux_synthesizes(kwargs, hdl_synth):
    comp = Mux(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "mux_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
