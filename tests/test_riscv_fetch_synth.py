"""Yosys synthesizability smoke test for ``FetchUnit``."""

import pytest

from myhdl_addons.riscv import FetchUnit


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_synthesizes(depth, hdl_synth):
    comp = FetchUnit(fetch_buffer=depth)
    result = hdl_synth(comp.hdl(comp.ports()), f"fetch_synth_{depth}")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
