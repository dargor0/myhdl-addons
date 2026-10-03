"""Conversion smoke test for the ``PriorityEncoder`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import PriorityEncoder


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [0, 1])
def test_priorityencoder_converts(hdl, registered, convert_dut):
    comp = PriorityEncoder(n=4, en=True, registered=registered)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"priorityencoder_r{registered}_{hdl.lower()}")
