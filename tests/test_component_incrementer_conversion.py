"""Conversion smoke test for the ``Incrementer`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Incrementer


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [0, 1])
def test_incrementer_converts(hdl, registered, convert_dut):
    comp = Incrementer(width=8, steps=(1, 2), registered=registered)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"incrementer_r{registered}_{hdl.lower()}")
