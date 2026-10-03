"""Conversion smoke test for the ``Counter`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Counter


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_counter_converts(hdl, convert_dut):
    comp = Counter(width=4, steps=(1, 2), max=10)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"counter_{hdl.lower()}")
