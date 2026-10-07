"""Unified exception hierarchy for ``myhdl_addons`` (single source of truth).

Every custom exception used by the sub-packages is **defined here** and
re-exported by the sub-packages that need it, so there is exactly one place
to look for and to extend the hierarchy::

    HdlError
    ├── HdlConfigError
    │   └── BusConfigError
    │       ├── WishboneConfigError
    │       ├── AxiConfigError
    │       └── RiscvConfigError
    ├── HdlTypeError
    │   └── BusTypeError
    │       ├── WishboneTypeError
    │       ├── AxiTypeError
    │       └── RiscvTypeError
    └── HdlProtocolError
        └── BusProtocolError
            └── AxiProtocolError

Each per-library error *also* inherits from a library base
(``WishboneError`` / ``AxiError`` / ``RiscvError``), so callers may catch
either the generic category (e.g. ``HdlConfigError``), the bus category
(``BusConfigError``) or the library category (``WishboneConfigError``).
"""

__all__ = [
    "AxiConfigError",
    "AxiError",
    "AxiProtocolError",
    "AxiTypeError",
    "BusConfigError",
    "BusError",
    "BusProtocolError",
    "BusTypeError",
    "ErrorType",
    "HdlConfigError",
    "HdlError",
    "HdlProtocolError",
    "HdlTypeError",
    "RiscvConfigError",
    "RiscvError",
    "RiscvTypeError",
    "WishboneConfigError",
    "WishboneError",
    "WishboneTypeError",
]


class HdlError(Exception):
    """Root of every ``myhdl_addons`` exception."""


class HdlConfigError(HdlError):
    """Invalid, unknown or inconsistent elaboration-time configuration."""


class HdlTypeError(HdlError):
    """A signal, port or value has an unexpected MyHDL type."""


class HdlProtocolError(HdlError):
    """A protocol rule was violated (elaboration or simulation time)."""


class BusError(HdlError):
    """Base class for the protocol-agnostic bus layer."""


class BusConfigError(HdlConfigError, BusError):
    """Invalid bus / interconnect / register configuration."""


class BusTypeError(HdlTypeError, BusError):
    """A bus signal or port object has an unexpected MyHDL type."""


class BusProtocolError(HdlProtocolError, BusError):
    """A bus protocol rule was violated."""


class WishboneError(BusError):
    """Base class for Wishbone library errors."""


class WishboneConfigError(BusConfigError, WishboneError):
    """Invalid Wishbone configuration (elaboration time)."""


class WishboneTypeError(BusTypeError, WishboneError):
    """A Wishbone signal does not have the expected MyHDL type."""


class AxiError(BusError):
    """Base class for AXI library errors."""


class AxiConfigError(BusConfigError, AxiError):
    """Invalid AXI configuration (elaboration time)."""


class AxiTypeError(BusTypeError, AxiError):
    """An AXI signal does not have the expected MyHDL type."""


class AxiProtocolError(BusProtocolError, AxiError):
    """An AXI protocol assertion failed (simulation time)."""


class RiscvError(BusError):
    """Base class for RISC-V core library errors (``RC-FR-008``)."""


class RiscvConfigError(BusConfigError, RiscvError):
    """Invalid RISC-V core configuration (elaboration time)."""


class RiscvTypeError(BusTypeError, RiscvError):
    """A RISC-V signal/port object has an unexpected MyHDL type."""


#: The type of an exception *class* deriving from :class:`HdlError`.  Usable as
#: an annotation for an ``exc=`` parameter (e.g. the shared validators, which
#: let a caller pick which concrete error class to raise).
ErrorType = type[HdlError]
