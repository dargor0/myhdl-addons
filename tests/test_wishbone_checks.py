"""Elaboration-time check tests (WB-FR-091 / WB-NFR-015, incl. negatives)."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.wishbone.checks import (
    WishboneConfigError,
    WishboneTypeError,
    check_address_range,
    check_signal_type,
    check_signal_width,
    check_widths,
)


def test_check_widths_ok():
    check_widths(32, 16, 8)
    check_widths(8, 8, 8)
    check_widths(64, 32, 16)


@pytest.mark.parametrize(
    "dw,aw,g",
    [
        (33, 16, 8),  # data_width not a multiple of gran
        (32, 16, 3),  # gran not a divisor
        (0, 16, 8),  # non-positive data_width
        (32, 16, 64),  # gran > data_width
        (32, -1, 8),  # non-positive adr_width
    ],
)
def test_check_widths_bad(dw, aw, g):
    with pytest.raises(WishboneConfigError):
        check_widths(dw, aw, g)


def test_check_signal_type_ok():
    check_signal_type(Signal(bool(0)), "ctrl", kind="bool")
    check_signal_type(Signal(intbv(0)[8:]), "bus", kind="intbv")


def test_check_signal_type_negative():
    with pytest.raises(WishboneTypeError):
        check_signal_type(Signal(intbv(0)[8:]), "bus", kind="bool")
    with pytest.raises(WishboneTypeError):
        check_signal_type(Signal(bool(0)), "ctrl", kind="intbv")
    with pytest.raises(WishboneTypeError):
        check_signal_type(42, "notasignal", kind="bool")


def test_check_signal_type_unknown_kind():
    with pytest.raises(WishboneConfigError):
        check_signal_type(Signal(bool(0)), "ctrl", kind="weird")


def test_check_signal_width():
    check_signal_width(Signal(intbv(0)[16:]), "adr", 16)
    with pytest.raises(WishboneTypeError):
        check_signal_width(Signal(intbv(0)[16:]), "adr", 8)


def test_check_address_range_negative():
    with pytest.raises(WishboneConfigError):
        check_address_range(0xF0, 0x20, 8)  # exceeds 8-bit space
    with pytest.raises(WishboneConfigError):
        check_address_range(0, 0, 16)  # zero size
