"""Yosys synthesizability smoke test for ``InstructionDecoder``."""

from myhdl_addons.riscv import InstructionDecoder


def test_decoder_synthesizes(hdl_synth):
    comp = InstructionDecoder()
    result = hdl_synth(comp.hdl(comp.ports()), "decoder_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
