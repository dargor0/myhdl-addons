"""Yosys synthesizability smoke test for ``MemoryRouter``."""

import pytest
from test_riscv_router import _router
from test_riscv_router_external import _contents, _regions

from myhdl_addons.riscv import MemoryRouter


@pytest.mark.parametrize("external", [False, True])
def test_router_synthesizes(external, hdl_synth):
    if external:
        comp = MemoryRouter(_regions(), contents=_contents())
    else:
        comp = _router()
    result = hdl_synth(comp.hdl(comp.ports()), f"router_synth_{int(external)}")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
