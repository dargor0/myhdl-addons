"""Conversion smoke test for the ``RegisterFile`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import RegisterFile


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_registerfile_converts(hdl, convert_dut):
    comp = RegisterFile(width=8, depth=4, read_ports=2, write_ports=1, read_latency=1)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"registerfile_{hdl.lower()}")
