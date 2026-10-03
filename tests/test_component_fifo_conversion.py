"""Conversion smoke test for the ``Fifo`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Fifo


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_fifo_converts(hdl, convert_dut):
    comp = Fifo(width=8, depth=4, interface="stream", fall_through=True)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"fifo_{hdl.lower()}")
