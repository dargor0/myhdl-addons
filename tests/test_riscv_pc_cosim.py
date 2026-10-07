"""Verilog cosimulation smoke test for ``ProgramCounter`` (Option A)."""

from test_riscv_pc import _actions, _python_device, _run

_RESET_VALUE = 0x1000


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name)

    return _make


def test_program_counter_cosim_matches_python(hdl_cosim):
    actions = _actions()
    python = _run(_python_device, _RESET_VALUE, actions)
    cosim = _run(_cosim_device(hdl_cosim, "pc_cosim"), _RESET_VALUE, actions)
    assert cosim == python
