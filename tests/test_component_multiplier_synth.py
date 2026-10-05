"""Yosys synthesizability smoke test for the ``Multiplier`` (S1)."""

import pytest

from myhdl_addons.components import Multiplier


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 1},
        {"width": 8},
        {"width": 8, "signed": False},
        {"width": 8, "impl": "luts"},
        {"width": 8, "impl": "luts", "dsptype": "9x9"},  # dsptype ignored
        {"width": 9},
        {"width": 10, "dsptype": "9x9"},  # ragged chunk
        {"width": 18},
        {"width": 18, "signed": False},
        {"width": 18, "dsptype": "9x9"},
        {"width": 25, "dsptype": "18x18"},
    ],
)
def test_multiplier_synthesizes(kwargs, hdl_synth):
    comp = Multiplier(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "mult_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
