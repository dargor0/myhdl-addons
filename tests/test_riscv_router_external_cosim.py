"""Verilog cosimulation for the router's external path (Option A).

Only the router is converted; the ``BusMaster`` and its behavioural slave stay
in Python and drive the router's ``*_bus_*`` client ports.
"""

from test_riscv_router_external import _OPS, _python_device, _run


def _cosim_router(hdl_cosim, name):
    def _make(router, ports):
        return hdl_cosim(router.hdl(ports), ports, name, initial_values=True)

    return _make


def test_router_external_cosim_matches_python(hdl_cosim):
    python = _run(_python_device, _python_device, _OPS)
    cosim = _run(_cosim_router(hdl_cosim, "router_ext_cosim"), _python_device, _OPS)
    assert cosim == python
