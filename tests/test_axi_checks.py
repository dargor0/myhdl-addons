"""AXI elaboration-time checks (AX-FR-101/009)."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.axi.checks import (
    AxiConfigError,
    AxiError,
    AxiTypeError,
    check_byte_enables,
    check_signal_width,
    check_variant,
    check_widths,
)
from myhdl_addons.bus_common import BusTypeError


def test_error_hierarchy():
    assert issubclass(AxiError, Exception)
    assert issubclass(AxiConfigError, AxiError)
    assert issubclass(AxiTypeError, AxiError)


def test_check_widths_ok():
    check_widths(32, 32, 4, 0, "full")
    check_widths(64, 64, 8, 0, "lite")


@pytest.mark.parametrize(
    "dw,aw,iw,uw,v",
    [
        (12, 32, 4, 0, "full"),  # data not multiple of 8
        (0, 32, 4, 0, "full"),  # zero data width
        (32, 0, 4, 0, "full"),  # zero addr width
        (128, 32, 4, 0, "lite"),  # lite must be 32/64
        (32, 32, 4, -1, "full"),  # negative user width
        (32, 32, 4, 0, "weird"),  # unknown variant
    ],
)
def test_check_widths_bad(dw, aw, iw, uw, v):
    with pytest.raises(AxiConfigError):
        check_widths(dw, aw, iw, uw, v)


def test_check_variant():
    assert check_variant("full") == "full"
    with pytest.raises(AxiConfigError):
        check_variant("axi3")


def test_signal_width_checks():
    check_signal_width(Signal(intbv(0)[32:]), "wdata", 32)
    with pytest.raises(AxiTypeError):
        check_signal_width(Signal(intbv(0)[32:]), "wdata", 16)
    with pytest.raises(AxiTypeError):
        check_signal_width(Signal(bool(0)), "wdata", 1)


def test_byte_enables():
    check_byte_enables(Signal(intbv(0)[4:]), "wstrb", 32)
    with pytest.raises(AxiTypeError):
        check_byte_enables(Signal(intbv(0)[8:]), "wstrb", 32)
    with pytest.raises(AxiTypeError):
        check_byte_enables(Signal(bool(0)), "wstrb", 32)


def test_bustypeerror_is_common():
    assert issubclass(AxiTypeError, BusTypeError)
