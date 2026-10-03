"""Conversion smoke test for the ``BarrelShifter`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import BarrelShifter


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [0, 1])
def test_barrelshifter_converts(hdl, registered, convert_dut):
    comp = BarrelShifter(width=8, registered=registered, en=bool(registered))
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"barrelshifter_r{registered}_{hdl.lower()}")
