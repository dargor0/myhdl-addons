"""Conversion smoke tests for ``BranchUnit`` and ``jalr_target`` (``RC-FR-023``)."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.riscv import BranchUnit, jalr_target


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_branch_unit_converts(hdl, convert_dut):
    comp = BranchUnit(width=8)
    convert_dut(comp.hdl(comp.ports()), hdl, f"branch_{hdl.lower()}")


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_jalr_target_converts(hdl, convert_dut):
    addr_i = Signal(intbv(0)[32:])
    jalr = Signal(bool(0))
    addr_o = Signal(intbv(0)[32:])
    convert_dut(jalr_target(addr_i, jalr, addr_o), hdl, f"jalr_target_{hdl.lower()}")
