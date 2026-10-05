"""Sequential multiplier configuration (``MD-FR-020..025``)."""

import pytest

from myhdl_addons.components import (
    AVAIL_RADIX,
    HdlConfigError,
    SequentialMultiplier,
)


def test_as_dict_and_repr():
    comp = SequentialMultiplier(width=16, signed=False, radix=4, en=True)
    info = comp.as_dict()
    assert info["width"] == 16
    assert info["signed"] is False
    assert info["radix"] == 4
    assert info["en"] is True
    assert "SequentialMultiplier" in repr(comp)


def test_available_radices():
    assert set(AVAIL_RADIX) == {2, 4}


def test_reset_value_is_masked():
    comp = SequentialMultiplier(width=4, reset_value=0x1FF)
    assert comp.as_dict()["reset_value"] == 0xFF


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        SequentialMultiplier(width=0)
    with pytest.raises(HdlConfigError):
        SequentialMultiplier(radix=3)
    with pytest.raises(HdlConfigError):
        SequentialMultiplier(en="yes")
    with pytest.raises(HdlConfigError):
        SequentialMultiplier(reset_value=-1)


def test_registered_reset_signal_is_used():
    from myhdl import ResetSignal

    rst = ResetSignal(0, active=0, isasync=False)
    comp = SequentialMultiplier(width=8, reset_signal=rst)
    assert comp.ports().reset is rst


def test_configuration_matrix():
    for component in (
        SequentialMultiplier(width=8),
        SequentialMultiplier(width=8, radix=4, signed=False, en=True),
        SequentialMultiplier(width=18, reset_value=1),
    ):
        assert component.hdl(component.ports()) is not None
