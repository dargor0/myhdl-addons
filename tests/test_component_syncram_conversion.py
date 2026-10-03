"""Conversion smoke test for the ``SyncRam`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import SyncRam


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_syncram_converts(hdl, convert_dut):
    comp = SyncRam(width=8, depth=4, read_latency=1, output_register=True)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"syncram_{hdl.lower()}")
