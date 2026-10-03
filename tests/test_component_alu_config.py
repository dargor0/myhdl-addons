"""Alu configuration and validation (``IC-FR-010..019``)."""

import pytest

from myhdl_addons.components import Alu, HdlConfigError


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        Alu(width=0)


def test_configuration_matrix():
    for component in (
        Alu(width=8),
        Alu(
            width=8,
            registered=1,
            en=True,
            ops=["ADD", "SUB"],
            flags=["zero", "carry"],
        ),
    ):
        assert component.hdl(component.ports()) is not None
