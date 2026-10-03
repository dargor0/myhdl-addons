"""Conversion smoke test for the ``Decoder`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Decoder


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [0, 1])
def test_decoder_converts(hdl, registered, convert_dut):
    comp = Decoder(n=4, en=True, registered=registered)
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"decoder_r{registered}_{hdl.lower()}")
