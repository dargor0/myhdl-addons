"""Conversion smoke test for the ``OneHotMux`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import OneHotMux


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("strict", [False, True])
def test_onehotmux_converts(hdl, registered, strict, convert_dut):
    comp = OneHotMux(
        width=8,
        n=3,
        valid=True,
        strict=strict,
        registered=registered,
        en=registered,
    )
    convert_dut(
        comp.hdl(comp.ports()),
        hdl,
        f"onehotmux_{strict}_{registered}_{hdl.lower()}",
    )
