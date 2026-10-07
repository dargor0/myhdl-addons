"""Yosys synthesizability smoke test for ``LoadStoreUnit``."""

from myhdl_addons.riscv import LoadStoreUnit


def test_lsu_synthesizes(hdl_synth):
    comp = LoadStoreUnit()
    result = hdl_synth(comp.hdl(comp.ports()), "lsu_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
