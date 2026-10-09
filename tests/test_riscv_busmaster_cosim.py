"""Verilog cosimulation smoke test for ``BusMaster`` (Option A)."""

from test_riscv_busmaster import _mem, _python_device, _run

from myhdl_addons.riscv import BusMaster


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name, initial_values=True)

    return _make


_OPS = [
    {"client": "c0", "addr": 0x04, "size": 2},
    {"client": "c1", "addr": 0x10, "we": 1, "wdata": 0x12345678, "size": 2},
    {"client": "c0", "addr": 0x10, "size": 2},
    {"client": "c1", "addr": 0x11, "we": 1, "wdata": 0x9A, "size": 0},
    {"client": "c1", "addr": 0x10, "size": 2},
]


def test_busmaster_cosim_matches_python(hdl_cosim):
    python = _run(_python_device, _OPS, _mem())
    cosim = _run(_cosim_device(hdl_cosim, "busmaster_cosim"), _OPS, _mem(), BusMaster())
    assert cosim == python
