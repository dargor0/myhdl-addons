"""Conversion smoke test for the ``Alu`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Alu


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [0, 1])
def test_alu_converts(hdl, registered, convert_dut):
    comp = Alu(width=8, registered=registered, en=bool(registered))
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"alu_r{registered}_{hdl.lower()}")
