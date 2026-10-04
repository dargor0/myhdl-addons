"""Common bus exception hierarchy (re-exported from :mod:`myhdl_addons.common`).

The exception classes themselves live in the single shared location
``myhdl_addons.common.errors``; this module only re-exports the bus-level
aliases so existing ``from .errors import BusConfigError`` imports keep
working.  See ``reqs/00_common_bus_lib.md``.
"""

from ..common.errors import (
    BusConfigError,
    BusError,
    BusProtocolError,
    BusTypeError,
)

__all__ = ["BusConfigError", "BusError", "BusProtocolError", "BusTypeError"]
