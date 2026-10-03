"""Conversion smoke test for the ``AddressDecoder`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import AddressDecoder


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [0, 1])
def test_addressdecoder_converts(hdl, registered, convert_dut):
    comp = AddressDecoder(
        adr_width=8,
        windows=((0x00, 0x10), (0x20, 0x10), (0x40, 0x20)),
        en=True,
        valid=True,
        registered=registered,
    )
    dut = comp.hdl(comp.ports())
    convert_dut(dut, hdl, f"addressdecoder_r{registered}_{hdl.lower()}")
