"""Yosys synthesizability smoke test for ``ImmGen`` (``RC-FR-022``)."""

from myhdl_addons.riscv import ImmGen


def test_immgen_synthesizes(hdl_synth):
    comp = ImmGen()
    result = hdl_synth(comp.hdl(comp.ports()), "immgen_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
