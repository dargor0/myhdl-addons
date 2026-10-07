"""Conversion smoke test for ``RvcDecompressor`` (``RC-FR-042``)."""

import pytest

from myhdl_addons.riscv import RvcDecompressor


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_rvc_decompressor_converts(hdl, convert_dut):
    comp = RvcDecompressor()
    convert_dut(comp.hdl(comp.ports()), hdl, f"rvc_{hdl.lower()}")
