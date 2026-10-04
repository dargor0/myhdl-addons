"""Yosys synthesizability smoke test for ``OneHotMux`` (S1)."""

import pytest

from myhdl_addons.components import OneHotMux


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "n": 3},
        {"width": 8, "n": 5, "valid": True},
        {"width": 8, "n": 3, "valid": True, "strict": True},
        {"width": 8, "n": 4, "registered": True, "en": True, "valid": True},
        {"width": 8, "n": 1},
    ],
)
def test_onehotmux_synthesizes(kwargs, hdl_synth):
    comp = OneHotMux(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "onehot_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
