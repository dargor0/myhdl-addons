"""Yosys synthesizability smoke test for ``Fifo``."""

import pytest

from myhdl_addons.components import STREAM, Fifo


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "depth": 2, "fall_through": True},
        {"width": 8, "depth": 2, "fall_through": False},
        {"width": 8, "depth": 4, "interface": STREAM, "fall_through": True},
        {"width": 8, "depth": 4, "count": True, "flush": True, "almost_full": 2},
        {"width": 8, "depth": 4, "registered_outputs": True},
    ],
)
def test_fifo_synthesizes(kwargs, hdl_synth):
    comp = Fifo(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "fifo_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
