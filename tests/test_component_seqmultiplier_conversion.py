"""Conversion smoke test for ``SequentialMultiplier`` (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import SequentialMultiplier


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("radix", [2, 4])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("en", [False, True])
def test_seqmultiplier_converts(hdl, radix, signed, en, convert_dut):
    comp = SequentialMultiplier(width=8, radix=radix, signed=signed, en=en)
    name = f"seqmul_{radix}_{int(signed)}_{int(en)}_{hdl.lower()}"
    convert_dut(comp.hdl(comp.ports()), hdl, name)
