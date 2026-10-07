"""Yosys synthesizability smoke test for ``SyncRom``."""

import pytest

from myhdl_addons.components import SyncRom


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "depth": 4, "init": [0x10, 0x20, 0x30, 0x40]},
        {"width": 8, "depth": 4, "init": [0x10, 0x20, 0x30, 0x40], "read_latency": 0},
        {
            "width": 8,
            "depth": 4,
            "init": [0x10, 0x20, 0x30, 0x40],
            "output_register": True,
        },
        {"width": 8, "depth": 4, "init": [0x10, 0x20, 0x30, 0x40], "read_ports": 2},
    ],
)
def test_syncrom_synthesizes(kwargs, hdl_synth):
    comp = SyncRom(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "syncrom_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
