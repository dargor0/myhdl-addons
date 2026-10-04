"""Common check framework and elaboration checks (CB-FR-100..103)."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.bus_common.checks import (
    DEFAULT_CHECKS,
    Check,
    CheckRegistry,
    Severity,
    check_address_range,
    check_signal_direction,
    check_signal_type,
    check_signal_width,
)
from myhdl_addons.bus_common.errors import BusConfigError, BusTypeError


def test_check_signal_type_ok():
    check_signal_type(Signal(bool(0)), "ctrl", kind="bool")
    check_signal_type(Signal(intbv(0)[8:]), "bus", kind="intbv")


def test_check_signal_type_negative():
    with pytest.raises(BusTypeError):
        check_signal_type(Signal(intbv(0)[8:]), "bus", kind="bool")
    with pytest.raises(BusTypeError):
        check_signal_type(Signal(bool(0)), "ctrl", kind="intbv")
    with pytest.raises(BusTypeError):
        check_signal_type(42, "notasignal", kind="bool")


def test_check_signal_type_unknown_kind():
    with pytest.raises(BusConfigError):
        check_signal_type(Signal(bool(0)), "ctrl", kind="weird")


def test_check_signal_width():
    check_signal_width(Signal(intbv(0)[16:]), "adr", 16)
    with pytest.raises(BusTypeError):
        check_signal_width(Signal(intbv(0)[16:]), "adr", 8)


class _View:
    def __init__(self):
        self.adr_o = Signal(intbv(0)[8:])
        self.cyc_i = None
        self.bad_o = 5


def test_check_signal_direction():
    view = _View()
    assert check_signal_direction(view, "adr", "out") is view.adr_o
    assert check_signal_direction(view, "cyc", "in") is None
    with pytest.raises(BusTypeError):
        check_signal_direction(view, "we", "out")
    with pytest.raises(BusTypeError):
        check_signal_direction(view, "bad", "out")
    with pytest.raises(BusConfigError):
        check_signal_direction(view, "adr", "sideways")


def test_check_address_range():
    check_address_range(0x00, 0x100, 16)
    with pytest.raises(BusConfigError):
        check_address_range(0xF0, 0x20, 8)
    with pytest.raises(BusConfigError):
        check_address_range(0, 0, 16)
    with pytest.raises(BusConfigError):
        check_address_range(-1, 0x10, 16)
    with pytest.raises(BusConfigError):
        check_address_range(0, None, 16)
    with pytest.raises(BusConfigError):
        check_address_range(0, "x", 16)
    with pytest.raises(BusConfigError):
        check_address_range("x", 0x10, 16)


def test_check_wrapper_and_registry():
    registry = CheckRegistry()
    check = Check("is_positive", lambda v: v > 0, severity=Severity.WARNING)
    registry.register(check)
    assert registry.get("is_positive") is check
    assert "is_positive" in registry
    assert len(registry) == 1
    assert registry.names() == ["is_positive"]
    assert next(iter(registry)) is check
    assert registry.run("is_positive", 3) is True

    with pytest.raises(BusConfigError):
        registry.register(Check("is_positive", lambda v: v))
    with pytest.raises(BusConfigError):
        registry.register("not a check")
    with pytest.raises(BusConfigError):
        registry.get("nope")

    registry.disable("is_positive")
    assert registry.run("is_positive", -1) is None
    registry.enable("is_positive")
    assert registry.run("is_positive", -1) is False

    assert registry.unregister("is_positive") is check
    assert registry.unregister("is_positive") is None


def test_check_registry_global_disable():
    registry = CheckRegistry()
    registry.register(Check("always", lambda: True))
    registry.disable()
    assert registry.run("always") is None
    registry.enable()
    assert registry.run("always") is True


def test_default_checks_registry():
    assert set(DEFAULT_CHECKS.names()) == {
        "signal_type",
        "signal_width",
        "signal_direction",
        "address_range",
    }

    DEFAULT_CHECKS.disable()
    assert DEFAULT_CHECKS.run("signal_type", 5, "ctrl") is None
    DEFAULT_CHECKS.enable()

    with pytest.raises(BusTypeError):
        DEFAULT_CHECKS.run("signal_type", 5, "ctrl")

    DEFAULT_CHECKS.disable("signal_type")
    assert DEFAULT_CHECKS.run("signal_type", 5, "ctrl") is None
    DEFAULT_CHECKS.enable("signal_type")
    with pytest.raises(BusTypeError):
        DEFAULT_CHECKS.run("signal_type", 5, "ctrl")
