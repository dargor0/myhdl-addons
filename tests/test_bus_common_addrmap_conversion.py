"""Conversion smoke test for the common address decoder (Verilog + VHDL).

The decoder's public API takes a *list* of select signals, which MyHDL does not
allow as a top-level port; it is therefore converted embedded in a parent block.
"""

import pytest
from myhdl import Signal, block, intbv

from myhdl_addons.bus_common.addrmap import address_decoder


@block
def _addrdec_top(adr, sel0, sel1, sel2):
    return address_decoder(
        adr, [sel0, sel1, sel2], [0x00, 0x20, 0x40], [0x10, 0x10, 0x20]
    )


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_address_decoder_converts(hdl, convert_dut):
    adr = Signal(intbv(0)[8:])
    selects = [Signal(bool(0)) for _ in range(3)]
    dut = _addrdec_top(adr, *selects)
    convert_dut(dut, hdl, f"bus_addrdec_{hdl.lower()}")
