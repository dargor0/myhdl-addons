"""Verilog cosimulation smoke test for ``MemoryRouter`` (Option A)."""

from test_riscv_router import _python_device, _router, _run


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name, initial_values=True)

    return _make


_OPS = [
    {"client": "f", "addr": 0x04, "size": 2},
    {"client": "d", "addr": 0x00, "size": 2},
    {"client": "d", "addr": 0x10, "we": 1, "wdata": 0xCAFEBABE, "size": 2},
    {"client": "f", "addr": 0x10, "size": 2},
    {"client": "d", "addr": 0x13, "we": 1, "wdata": 0x0000005A, "size": 0},
    {"client": "d", "addr": 0x10, "size": 2},
    {"client": "f", "addr": 0x20, "size": 2},  # fault: io has no I
]


def test_router_cosim_matches_python(hdl_cosim):
    python = _run(_python_device, _OPS)
    cosim = _run(_cosim_device(hdl_cosim, "router_cosim"), _OPS, _router())
    assert cosim == python
