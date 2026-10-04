"""Elaboration-time checks for the AXI library.

The library performs its own signal/port checks (``AX-FR-101``) and does not
depend on an external typing library.  The error hierarchy extends the common
``BusError`` (``AX-FR-009``).
"""

from __future__ import annotations

from myhdl import intbv

from ..bus_common import check_multiple_of, check_positive_int
from ..common.errors import (
    AxiConfigError,
    AxiError,
    AxiProtocolError,
    AxiTypeError,
    BusConfigError,
    BusTypeError,
)

__all__ = [
    "VARIANTS",
    "AxiConfigError",
    "AxiError",
    "AxiProtocolError",
    "AxiTypeError",
    "check_widths",
]

VARIANTS = ("full", "lite", "stream")


def check_variant(variant: str) -> str:
    """Return *variant* if it is one of ``full``/``lite``/``stream``."""
    if variant not in VARIANTS:
        raise AxiConfigError(f"variant must be one of {VARIANTS}, got {variant!r}")
    return variant


def check_widths(
    data_width: int,
    addr_width: int,
    id_width: int = 4,
    user_width: int = 0,
    variant: str = "full",
) -> None:
    """Validate the fundamental AXI geometry.

    Raises:
        AxiConfigError: on any inconsistent width.
    """
    check_variant(variant)
    try:
        check_positive_int(data_width, "data_width")
        check_positive_int(addr_width, "addr_width")
        check_positive_int(id_width, "id_width")
        check_multiple_of(data_width, 8, "data_width")
    except BusConfigError as exc:
        raise AxiConfigError(str(exc)) from exc
    if variant == "lite" and data_width not in (32, 64):
        raise AxiConfigError(f"AXI4-Lite data_width must be 32 or 64, got {data_width}")
    if user_width < 0:
        raise AxiConfigError(f"user_width must be >= 0, got {user_width!r}")


def check_signal_width(sig: object, name: str, width: int) -> None:
    """Check that an ``intbv`` signal has exactly *width* bits."""
    from ..bus_common import check_signal_width as _csw

    try:
        _csw(sig, name, width)
    except BusTypeError as exc:
        raise AxiTypeError(str(exc)) from exc


def check_byte_enables(sig: object, name: str, data_width: int) -> None:
    """Check that a ``WSTRB``-style signal has ``data_width/8`` bits."""
    if not isinstance(getattr(sig, "val", None), intbv):
        raise AxiTypeError(f"{name}: expected an intbv signal")
    check_signal_width(sig, name, data_width // 8)
