"""SyncRom configuration and validation (``IC-FR-140..144``)."""

import pytest

from myhdl_addons.components import HdlConfigError, SyncRom


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        SyncRom(width=8, depth=4, init=[1, 2])


def test_configuration_matrix():
    for component in (
        SyncRom(width=8, depth=4, init=[1, 2, 3, 4]),
        SyncRom(
            width=8,
            depth=4,
            init=[1, 2, 3, 4],
            read_latency=0,
            output_register=True,
            read_ports=2,
        ),
    ):
        assert component.hdl(component.ports()) is not None
