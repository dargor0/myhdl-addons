"""Yosys synthesizability smoke test for ``ToHost``."""

from myhdl_addons.riscv import ToHost


def test_tohost_synthesizes(hdl_synth):
    comp = ToHost()
    result = hdl_synth(comp.hdl(comp.ports()), "tohost_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
