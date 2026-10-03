"""Conversion smoke test for the ``Comparator`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import AVAIL_OUTPUTS, Comparator


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("registered", [False, True])
def test_comparator_converts(hdl, signed, registered, convert_dut):
    comp = Comparator(
        width=8,
        outputs=AVAIL_OUTPUTS,
        signed=signed,
        registered=registered,
        en=registered,
    )
    convert_dut(
        comp.hdl(comp.ports()),
        hdl,
        f"comparator_{signed}_{registered}_{hdl.lower()}",
    )
