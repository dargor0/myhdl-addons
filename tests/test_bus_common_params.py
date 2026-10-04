"""Common errors, parameter helpers and byte-enable helpers
(CB-FR-010..012, CB-FR-024)."""

import pytest

from myhdl_addons.bus_common.bits import all_enables, byte_count, enable_width
from myhdl_addons.bus_common.errors import (
    BusConfigError,
    BusError,
    BusProtocolError,
    BusTypeError,
)
from myhdl_addons.bus_common.params import (
    check_alignment,
    check_multiple_of,
    check_positive_int,
    check_power_of_two,
    check_range,
    get_preset,
    list_presets,
    register_preset,
)


def test_error_hierarchy():
    assert issubclass(BusConfigError, BusError)
    assert issubclass(BusTypeError, BusError)
    assert issubclass(BusProtocolError, BusError)
    assert issubclass(BusError, Exception)


def test_check_positive_int():
    assert check_positive_int(4, "x") == 4
    for bad in (0, -1, 3.0, True, "4"):
        with pytest.raises(BusConfigError):
            check_positive_int(bad, "x")


def test_check_power_of_two():
    assert check_power_of_two(1, "x") == 1
    assert check_power_of_two(8, "x") == 8
    for bad in (0, 3, -4, "8"):
        with pytest.raises(BusConfigError):
            check_power_of_two(bad, "x")


def test_check_multiple_of():
    assert check_multiple_of(16, 8, "x") == 16
    with pytest.raises(BusConfigError):
        check_multiple_of(12, 8, "x")
    with pytest.raises(BusConfigError):
        check_multiple_of(8, 0, "x")
    with pytest.raises(BusConfigError):
        check_multiple_of("8", 8, "x")


def test_check_range():
    assert check_range(3, 0, 4, "x") == 3
    with pytest.raises(BusConfigError):
        check_range(4, 0, 4, "x")
    with pytest.raises(BusConfigError):
        check_range(-1, 0, 4, "x")


def test_check_alignment():
    assert check_alignment(0x10, 0x4, "off") == 0x10
    with pytest.raises(BusConfigError):
        check_alignment(0x11, 0x4, "off")
    with pytest.raises(BusConfigError):
        check_alignment(0x10, 0, "off")


def test_preset_registry():
    register_preset("test_small", {"data_width": 8})
    assert get_preset("test_small") == {"data_width": 8}
    assert "test_small" in list_presets()
    with pytest.raises(BusConfigError):
        register_preset("test_small", {"data_width": 16})
    register_preset("test_small", {"data_width": 16}, overwrite=True)
    assert get_preset("test_small")["data_width"] == 16
    with pytest.raises(BusConfigError):
        get_preset("test_missing_preset")


def test_preset_registry_bad_input():
    with pytest.raises(BusConfigError):
        register_preset("", {})
    with pytest.raises(BusConfigError):
        register_preset("test_bad", [1, 2])


def test_byte_count():
    assert byte_count(8) == 1
    assert byte_count(32) == 4
    assert byte_count(64) == 8
    with pytest.raises(BusConfigError):
        byte_count(12)
    with pytest.raises(BusConfigError):
        byte_count(0)


def test_enable_width():
    assert enable_width(32, 8) == 4
    assert enable_width(32, 16) == 2
    assert enable_width(64, 8) == 8
    assert all_enables(32, 8) == 0xF
    assert all_enables(64, 16) == 0xF
    for dw, g in [(32, 3), (32, 64), (0, 8)]:
        with pytest.raises(BusConfigError):
            enable_width(dw, g)
