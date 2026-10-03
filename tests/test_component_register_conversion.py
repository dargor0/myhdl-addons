"""Conversion smoke test for the ``Register`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Register


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_register_converts(hdl, convert_dut):
    comp = Register(fields=(("a", 4), ("b", 8)), en=True, flush=True, load=True)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"register_{hdl.lower()}")
