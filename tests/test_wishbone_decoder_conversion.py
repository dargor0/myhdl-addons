"""Conversion smoke test for the Wishbone address decoder (Verilog + VHDL)."""

import pytest
from myhdl import Signal, block, intbv

from myhdl_addons.wishbone import address_decoder


@block
def _dec_top(adr, sel0, sel1, sel2):
    return address_decoder(
        adr, [sel0, sel1, sel2], [0x0000, 0x1000, 0x2000], [0x100, 0x100, 0x100]
    )


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_address_decoder_converts(hdl, convert_dut):
    adr = Signal(intbv(0)[16:])
    selects = [Signal(bool(0)) for _ in range(3)]
    convert_dut(_dec_top(adr, *selects), hdl, f"wb_addrdec_{hdl.lower()}")
