"""Verilog cosimulation smoke test for ``Register`` (Option A)."""

import pytest
from test_component_register_fields import (
    _capture_tb,
    _control_tb,
    _multi_tb,
    _python_device,
)


def _cosim_device(hdl_cosim, name):
    def _make(reg, ports):
        return hdl_cosim(reg.hdl(ports), ports, name)

    return _make


@pytest.mark.parametrize("bench", [_capture_tb, _control_tb, _multi_tb])
def test_register_cosim_matches_python(bench, hdl_cosim):
    python = []
    bench(_python_device, python).run_sim()
    cosim = []
    bench(_cosim_device(hdl_cosim, "reg_cosim"), cosim).run_sim()
    assert cosim == python
