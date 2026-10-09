"""Yosys synthesizability smoke test for ``BusMaster``."""

from myhdl_addons.riscv import BusMaster


def test_busmaster_synthesizes(hdl_synth):
    comp = BusMaster()
    result = hdl_synth(comp.hdl(comp.ports()), "busmaster_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
