"""Conversion smoke test for ``ImmGen`` (``RC-FR-022``)."""

import pytest

from myhdl_addons.riscv import ImmGen


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_immgen_converts(hdl, convert_dut):
    comp = ImmGen()
    convert_dut(comp.hdl(comp.ports()), hdl, f"immgen_{hdl.lower()}")
