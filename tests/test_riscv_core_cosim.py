"""Verilog cosimulation for ``RiscvCore`` (Option A).

The core is converted (with power-on memory values so the internal region is
preloaded) and driven by the same Python bench that runs the Python core.
"""

from test_riscv_core import _config, _i, _run, _s, _u

_PROGRAM = [
    _i(5, 0, 0, 1),  # addi x1, x0, 5
    _i(7, 0, 0, 2),  # addi x2, x0, 7
    _i(0, 1, 0, 3, 0x33) | (2 << 20),  # add x3, x1, x2
    _u(0x1000, 4),  # lui x4, 0x1
    _s(0, 3, 4, 2),  # sw x3, 0(x4) -> tohost
]


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name, initial_values=True)

    return _make


def test_core_cosim_matches_python(hdl_cosim, tmp_path):
    python = _run(_config(tmp_path, _PROGRAM))
    cosim = _run(
        _config(tmp_path, _PROGRAM),
        make_device=_cosim_device(hdl_cosim, "core_cosim"),
    )
    assert python == [(1, 12, 0, 0)]
    assert cosim == python
