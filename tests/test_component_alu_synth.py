"""Yosys synthesizability smoke test for the ``Alu`` (S1).

Technology-independent ``synth``; the test fails on any Yosys error or warning
so that non-synthesizable constructs surface immediately.
"""

import pytest

from myhdl_addons.components import Alu


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8},
        {"width": 8, "registered": 1, "en": True},
    ],
)
def test_alu_synthesizes(kwargs, hdl_synth):
    alu = Alu(**kwargs)
    result = hdl_synth(alu.hdl(alu.ports()), "alu_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
