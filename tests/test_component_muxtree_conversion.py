"""Conversion smoke test for ``MuxTree`` (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import MuxTree


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize(
    "width,n,policy,default,alias",
    [
        (8, 5, "const", 0, 0),
        (8, 5, "lastinput", 0, 0),
        (8, 5, "alias", 0, 1),
        (8, 5, "wrap", 0, 0),
        (8, 9, "wrap", 0, 0),  # large non-power-of-two
        (8, 8, "lastinput", 0, 0),  # power of two
        (8, 2, "lastinput", 0, 0),  # smallest multi-input power of two
        (4, 1, "lastinput", 0, 0),  # n == 1, no select
    ],
)
def test_muxtree_converts(hdl, width, n, policy, default, alias, convert_dut):
    comp = MuxTree(width=width, n=n, policy=policy, default_value=default, alias=alias)
    name = f"muxtree_{width}_{n}_{policy}_{hdl.lower()}"
    convert_dut(comp.hdl(comp.ports()), hdl, name)
