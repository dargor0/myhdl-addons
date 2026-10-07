"""Verilog cosimulation smoke test for ``ToHost`` (Option A)."""

from test_riscv_tohost import _python_device, _tohost_tb


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name)

    return _make


def _run(make_device):
    results = []
    _tohost_tb(make_device, results).run_sim()
    return results


def test_tohost_cosim_matches_python(hdl_cosim):
    assert _run(_cosim_device(hdl_cosim, "tohost_cosim")) == _run(_python_device)
