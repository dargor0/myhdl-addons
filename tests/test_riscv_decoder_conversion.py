"""Conversion smoke test for ``InstructionDecoder`` (``RC-FR-020``)."""

import pytest

from myhdl_addons.riscv import InstructionDecoder


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_decoder_converts(hdl, convert_dut):
    comp = InstructionDecoder()
    convert_dut(comp.hdl(comp.ports()), hdl, f"decoder_{hdl.lower()}")
