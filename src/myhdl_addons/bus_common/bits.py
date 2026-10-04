"""Byte-enable / granularity helpers.

Implements ``CB-FR-024``: derive the byte-lane count and the enable-signal
width from the data width and granularity, reused by all buses.
"""

from .errors import BusConfigError
from .params import check_multiple_of, check_positive_int

__all__ = ["all_enables", "byte_count", "enable_width"]


def _check_geometry(data_width: int, gran: int) -> None:
    check_positive_int(data_width, "data_width")
    check_positive_int(gran, "gran")
    check_multiple_of(data_width, 8, "data_width")
    check_multiple_of(gran, 8, "gran")
    if gran > data_width:
        raise BusConfigError(f"gran ({gran}) must not exceed data_width ({data_width})")
    check_multiple_of(data_width, gran, "data_width")


def byte_count(data_width: int) -> int:
    """Return the number of 8-bit bytes in a *data_width*-bit word."""
    check_positive_int(data_width, "data_width")
    check_multiple_of(data_width, 8, "data_width")
    return data_width // 8


def enable_width(data_width: int, gran: int = 8) -> int:
    """Return the number of enable bits (lanes) for the given geometry."""
    _check_geometry(data_width, gran)
    return data_width // gran


def all_enables(data_width: int, gran: int = 8) -> int:
    """Return an integer with every enable lane set."""
    return (1 << enable_width(data_width, gran)) - 1
