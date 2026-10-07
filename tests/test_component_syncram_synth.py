"""Yosys synthesizability smoke test for ``SyncRam``."""

import pytest

from myhdl_addons.components import WRITE_FIRST, SyncRam


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "depth": 4, "read_latency": 1},
        {"width": 8, "depth": 4, "read_latency": 0},
        {"width": 8, "depth": 4, "read_latency": 1, "write_mode": WRITE_FIRST},
        {"width": 8, "depth": 4, "read_latency": 1, "output_register": True},
        {"width": 8, "depth": 4, "read_latency": 1, "init": [1, 2, 3, 4]},
        {"width": 16, "depth": 4, "read_latency": 1, "byte_write": 2},
        {"width": 8, "depth": 4, "read_latency": 1, "read_ports": 2},
    ],
)
def test_syncram_synthesizes(kwargs, hdl_synth):
    comp = SyncRam(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "syncram_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
