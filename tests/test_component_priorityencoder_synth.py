"""Yosys synthesizability smoke test for ``PriorityEncoder`` (S1)."""

import pytest

from myhdl_addons.components import PriorityEncoder


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n": 4},
        {"n": 5},
        {"n": 4, "priority": "high"},
        {"n": 4, "en": True},
        {"n": 4, "registered": 1},
    ],
)
def test_priorityencoder_synthesizes(kwargs, hdl_synth):
    comp = PriorityEncoder(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "priorityencoder_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
