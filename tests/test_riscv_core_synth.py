"""Yosys synthesizability smoke test for ``RiscvCore``."""

from test_riscv_core import _config, _i, _s, _u

from myhdl_addons.riscv import RiscvCore

_PROGRAM = [_i(1, 0, 0, 1), _u(0x1000, 5), _s(0, 1, 5, 2)]


def test_core_synthesizes(hdl_synth, tmp_path):
    comp = RiscvCore(_config(tmp_path, _PROGRAM))
    result = hdl_synth(comp.hdl(comp.ports()), "core_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
