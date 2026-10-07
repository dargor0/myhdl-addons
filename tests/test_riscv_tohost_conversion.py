"""Conversion smoke test for ``ToHost`` (``RC-FR-111/113``)."""

import pytest

from myhdl_addons.riscv import ToHost


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_tohost_converts(hdl, convert_dut):
    comp = ToHost()
    convert_dut(comp.hdl(comp.ports()), hdl, f"tohost_{hdl.lower()}")
