"""Yosys synthesizability smoke test for ``RegisterFile``."""

import pytest

from myhdl_addons.components import NO_CHANGE, WRITE_FIRST, RegisterFile


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "depth": 4, "read_ports": 2, "write_ports": 1, "read_latency": 0},
        {
            "width": 8,
            "depth": 4,
            "read_ports": 1,
            "write_ports": 1,
            "read_latency": 1,
            "write_mode": WRITE_FIRST,
        },
        {
            "width": 8,
            "depth": 4,
            "read_ports": 1,
            "write_ports": 1,
            "read_latency": 1,
            "write_mode": NO_CHANGE,
        },
        {"width": 8, "depth": 4, "zero_reg_fix_value": 0, "read_latency": 0},
        {"width": 16, "depth": 4, "byte_write": True, "read_latency": 0},
        {
            "width": 8,
            "depth": 8,
            "reset_enable": False,
            "init": [1, 2, 3, 4, 5, 6, 7, 8],
            "read_latency": 0,
        },
    ],
)
def test_registerfile_synthesizes(kwargs, hdl_synth):
    comp = RegisterFile(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "regfile_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
