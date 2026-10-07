"""Conversion smoke test for ``ProgramCounter`` (``RC-FR-029``)."""

import pytest

from myhdl_addons.riscv import ProgramCounter


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_program_counter_converts(hdl, convert_dut):
    comp = ProgramCounter(reset_value=0x1000)
    convert_dut(comp.hdl(comp.ports()), hdl, f"pc_{hdl.lower()}")
