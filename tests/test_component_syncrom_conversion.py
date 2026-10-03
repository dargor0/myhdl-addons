"""Conversion smoke test for the ``SyncRom`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import SyncRom


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_syncrom_converts(hdl, convert_dut):
    comp = SyncRom(width=8, depth=4, init=[0, 1, 2, 3])
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"syncrom_{hdl.lower()}")
