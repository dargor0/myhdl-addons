"""Conversion smoke test for ``MemoryRouter`` (``RC-FR-105``)."""

import pytest
from test_riscv_router import _router
from test_riscv_router_external import _contents, _regions

from myhdl_addons.riscv import MemoryRouter


@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_router_converts(external, hdl, convert_dut):
    if external:
        comp = MemoryRouter(_regions(), contents=_contents())
    else:
        comp = _router()
    convert_dut(comp.hdl(comp.ports()), hdl, f"router_{int(external)}_{hdl.lower()}")
