"""Conversion smoke test for ``BusMaster`` (``RC-FR-100``)."""

import pytest

from myhdl_addons.riscv import BusMaster


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_busmaster_converts(hdl, convert_dut):
    comp = BusMaster()
    convert_dut(comp.hdl(comp.ports()), hdl, f"busmaster_{hdl.lower()}")
