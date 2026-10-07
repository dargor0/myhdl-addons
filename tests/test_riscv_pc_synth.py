"""Yosys synthesizability smoke test for ``ProgramCounter``."""

from myhdl_addons.riscv import ProgramCounter


def test_program_counter_synthesizes(hdl_synth):
    comp = ProgramCounter(reset_value=0x1000)
    result = hdl_synth(comp.hdl(comp.ports()), "pc_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
