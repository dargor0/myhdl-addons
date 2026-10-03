"""Conversion smoke test for the ``Mux`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Mux


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize("registered", [False, True])
@pytest.mark.parametrize("n", [1, 3, 5])
def test_mux_converts(hdl, registered, n, convert_dut):
    comp = Mux(
        width=8, n=n, default_value=0xEE, valid=True,
        registered=registered, en=registered,
    )
    convert_dut(
        comp.hdl(comp.ports()), hdl, f"mux_n{n}_{registered}_{hdl.lower()}"
    )
