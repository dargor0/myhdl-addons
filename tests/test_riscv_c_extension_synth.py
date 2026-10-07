"""Yosys synthesizability smoke test for the C front-end plug-in.

Confirms the decompressor elaborated through ``CExtension.front_end`` (via the
registry) is synthesizable, not only the directly-instantiated component.
"""

from myhdl import Signal, intbv

from myhdl_addons.common.views import SignalView
from myhdl_addons.riscv import default_registry


def test_c_extension_front_end_synthesizes(hdl_synth):
    registry = default_registry()
    registry.select(["c"])
    context = SignalView(
        instr_i=Signal(intbv(0)[16:]),
        instr_o=Signal(intbv(0)[32:]),
        illegal=Signal(bool(0)),
    )
    result = hdl_synth(registry.build(context)[0], "c_ext_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
