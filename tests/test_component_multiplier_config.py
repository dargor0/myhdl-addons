"""Combinational multiplier configuration (``MD-FR-001..007``)."""

import pytest

from myhdl_addons.components import (
    AVAIL_DSP_TYPES,
    AVAIL_MUL_IMPL,
    HdlConfigError,
    Multiplier,
)


def test_as_dict_and_repr():
    comp = Multiplier(width=16, signed=False, impl="luts", dsptype=None)
    info = comp.as_dict()
    assert info["width"] == 16
    assert info["signed"] is False
    assert info["impl"] == "luts"
    assert info["dsptype"] is None
    assert "Multiplier" in repr(comp)


def test_available_constants():
    assert set(AVAIL_MUL_IMPL) == {"dsp", "luts"}
    assert set(AVAIL_DSP_TYPES) == {"9x9", "18x18", "25x18", "27x18"}


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        Multiplier(width=0)
    with pytest.raises(HdlConfigError):
        Multiplier(impl="bogus")
    with pytest.raises(HdlConfigError):
        Multiplier(dsptype="7x7")
    with pytest.raises(HdlConfigError):
        Multiplier(signed="yes")


def test_configuration_matrix():
    for component in (
        Multiplier(width=8),
        Multiplier(width=8, signed=False, impl="luts"),
        Multiplier(width=18, dsptype="9x9"),
    ):
        assert component.hdl(component.ports()) is not None
