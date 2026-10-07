"""Yosys synthesizability smoke test for ``RvcDecompressor``.

Technology-independent ``synth``; the test fails on any Yosys error or warning
so that non-synthesizable constructs surface immediately.
"""

from myhdl_addons.riscv import RvcDecompressor


def test_rvc_decompressor_synthesizes(hdl_synth):
    rvc = RvcDecompressor()
    result = hdl_synth(rvc.hdl(rvc.ports()), "rvc_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
