"""Conversion smoke test for ``FetchUnit`` (``RC-FR-043``)."""

import pytest

from myhdl_addons.riscv import FetchUnit


@pytest.mark.parametrize("depth", [0, 1, 2])
@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_fetch_converts(depth, hdl, convert_dut):
    comp = FetchUnit(fetch_buffer=depth)
    convert_dut(comp.hdl(comp.ports()), hdl, f"fetch_{depth}_{hdl.lower()}")
