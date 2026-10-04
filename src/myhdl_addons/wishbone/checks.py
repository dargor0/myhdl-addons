"""Elaboration-time checks for the Wishbone library.

These checks implement requirement ``WB-FR-091`` (library-native signal /
port checks) and ``WB-NFR-015`` (the test suite must verify them, including
negative cases).  They run at *elaboration time* (plain Python), raise
``Wishbone*Error`` on failure, and are independent of any external typing
library.
"""

from myhdl import SignalType, intbv

from ..common.errors import (
    WishboneConfigError,
    WishboneError,
    WishboneTypeError,
)

__all__ = [
    "WishboneConfigError",
    "WishboneError",
    "WishboneTypeError",
    "check_signal_type",
    "check_signal_width",
    "check_widths",
]

#: data widths the library is tested with (WB-FR-111)
KNOWN_DATA_WIDTHS = (8, 16, 32, 64)
KNOWN_GRANULARITIES = (8, 16, 32, 64)


def check_widths(data_width: int, adr_width: int, gran: int) -> None:
    """Validate the fundamental bus parameters.

    Raises:
        WishboneConfigError: on any inconsistent width/granularity.
    """
    if not isinstance(data_width, int) or data_width <= 0:
        raise WishboneConfigError(
            f"data_width must be a positive int, got {data_width!r}"
        )
    if not isinstance(adr_width, int) or adr_width <= 0:
        raise WishboneConfigError(
            f"adr_width must be a positive int, got {adr_width!r}"
        )
    if not isinstance(gran, int) or gran <= 0:
        raise WishboneConfigError(f"gran must be a positive int, got {gran!r}")
    if gran > data_width:
        raise WishboneConfigError(
            f"gran ({gran}) must not exceed data_width ({data_width})"
        )
    if data_width % gran != 0:
        raise WishboneConfigError(
            f"data_width ({data_width}) must be a multiple of gran ({gran})"
        )


def check_signal_type(sig: object, name: str, kind: str = "bool") -> SignalType:
    """Check that *sig* is a MyHDL signal of the expected value type.

    Args:
        sig: object to check.
        name: name used in the error message.
        kind: ``"bool"`` (single-bit control) or ``"intbv"`` (bus).
    """
    if not isinstance(sig, SignalType):
        raise WishboneTypeError(
            f"{name}: expected a MyHDL signal, got {type(sig).__name__!r}"
        )
    if kind == "bool":
        if not isinstance(sig.val, bool):
            raise WishboneTypeError(
                f"{name}: expected Signal(bool), got Signal({type(sig.val).__name__})"
            )
    elif kind == "intbv":
        if not isinstance(sig.val, intbv):
            raise WishboneTypeError(
                f"{name}: expected Signal(intbv), got Signal({type(sig.val).__name__})"
            )
    else:
        raise WishboneConfigError(f"unknown signal kind {kind!r}")
    return sig


def check_signal_width(sig: object, name: str, width: int) -> SignalType:
    """Check that an ``intbv`` signal has exactly *width* bits."""
    check_signal_type(sig, name, kind="intbv")
    actual = len(sig.val)
    if actual != width:
        raise WishboneTypeError(
            f"{name}: expected {width}-bit signal, got {actual} bits"
        )
    return sig


def check_address_range(
    base: int, size: int | None, adr_width: int, name: str = "slave"
) -> None:
    """Check that a slave address window fits and is well-formed."""
    if base < 0:
        raise WishboneConfigError(f"{name}: base must be >= 0")
    if size is None:
        raise WishboneConfigError(f"{name}: size is required")
    if size <= 0:
        raise WishboneConfigError(f"{name}: size must be > 0")
    if base + size > (1 << adr_width):
        raise WishboneConfigError(
            f"{name}: window [0x{base:X}, 0x{base + size:X}) exceeds "
            f"the {adr_width}-bit address space"
        )
