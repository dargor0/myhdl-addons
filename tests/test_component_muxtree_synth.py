"""Yosys synthesizability smoke test for ``MuxTree`` (S1)."""

import pytest

from myhdl_addons.components import MuxTree


@pytest.mark.parametrize(
    "width,n,policy,default,alias",
    [
        (8, 5, "const", 0xAB, 0),
        (8, 5, "lastinput", 0, 0),
        (8, 5, "alias", 0, 1),
        (8, 5, "wrap", 0, 0),
        (8, 9, "wrap", 0, 0),
        (8, 8, "lastinput", 0, 0),
        (8, 2, "lastinput", 0, 0),
        (1, 4, "lastinput", 0, 0),
    ],
)
def test_muxtree_synthesizes(width, n, policy, default, alias, hdl_synth):
    comp = MuxTree(width=width, n=n, policy=policy, default_value=default, alias=alias)
    result = hdl_synth(comp.hdl(comp.ports()), f"muxtree_{width}_{n}_{policy}")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
