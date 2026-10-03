"""SyncRam configuration and validation (``IC-FR-100..107``)."""

import pytest

from myhdl_addons.components import HdlConfigError, SyncRam


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        SyncRam(width=8, depth=4, byte_write=3)


def test_configuration_matrix():
    for component in (
        SyncRam(width=8, depth=4),
        SyncRam(
            width=16,
            depth=4,
            read_latency=0,
            output_register=True,
            write_mode="write_first",
            byte_write=2,
            read_ports=2,
            write_ports=2,
            init=[1, 2, 3, 4],
        ),
        SyncRam(width=8, depth=4, read_latency=1, output_register=True),
    ):
        assert component.hdl(component.ports()) is not None
