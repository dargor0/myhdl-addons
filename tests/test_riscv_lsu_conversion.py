"""Conversion smoke test for ``LoadStoreUnit`` (``RC-FR-070..072``)."""

import pytest

from myhdl_addons.riscv import LoadStoreUnit


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_lsu_converts(hdl, convert_dut):
    comp = LoadStoreUnit()
    convert_dut(comp.hdl(comp.ports()), hdl, f"lsu_{hdl.lower()}")
