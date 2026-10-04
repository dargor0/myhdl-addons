"""Shared foundation for every ``myhdl_addons`` sub-package.

``myhdl_addons.common`` holds the code that is deliberately **not** specific
to components, buses or any other sub-package:

* :mod:`~myhdl_addons.common.errors` — the single, unified exception
  hierarchy (``HdlError`` and its ``Bus``/``Wishbone``/``Axi``/component
  descendants);
* :mod:`~myhdl_addons.common.config` — generic elaboration-time validators
  and the :class:`ComponentBase` introspection protocol;
* :mod:`~myhdl_addons.common.views` — the protocol-agnostic
  :class:`SignalView` and its ``connect`` copy-wiring helper.

Nothing here imports ``components``, ``bus_common``, ``wishbone`` or ``axi``;
the dependency arrow always points *into* ``common``.
"""

from .config import (
    ComponentBase,
    ceil_log2,
    check_alignment,
    check_bool,
    check_choice,
    check_int,
    check_multiple_of,
    check_non_negative,
    check_positive,
    check_power_of_two,
    check_range,
    check_registered,
    mask,
    normalize_subset,
)
from .errors import (
    AxiConfigError,
    AxiError,
    AxiProtocolError,
    AxiTypeError,
    BusConfigError,
    BusError,
    BusProtocolError,
    BusTypeError,
    ErrorType,
    HdlConfigError,
    HdlError,
    HdlProtocolError,
    HdlTypeError,
    WishboneConfigError,
    WishboneError,
    WishboneTypeError,
)
from .views import SignalView, connect

__all__ = [
    "AxiConfigError",
    "AxiError",
    "AxiProtocolError",
    "AxiTypeError",
    "BusConfigError",
    "BusError",
    "BusProtocolError",
    "BusTypeError",
    "ComponentBase",
    "ErrorType",
    "HdlConfigError",
    "HdlError",
    "HdlProtocolError",
    "HdlTypeError",
    "SignalView",
    "WishboneConfigError",
    "WishboneError",
    "WishboneTypeError",
    "ceil_log2",
    "check_alignment",
    "check_bool",
    "check_choice",
    "check_int",
    "check_multiple_of",
    "check_non_negative",
    "check_positive",
    "check_power_of_two",
    "check_range",
    "check_registered",
    "connect",
    "mask",
    "normalize_subset",
]
