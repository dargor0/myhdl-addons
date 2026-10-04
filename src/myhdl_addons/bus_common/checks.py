"""Common protocol-check framework and elaboration-time checks.

Implements ``CB-FR-100`` (registry with global/per-check enable-disable and
severity levels), ``CB-FR-101`` (the common signal/address checks reused by
per-bus assertion sets) and ``CB-FR-102`` (checks run only in Python and can
be disabled with no synthesized overhead).
"""

from collections.abc import Callable, Iterator
from enum import Enum
from typing import Any

from myhdl import SignalType, intbv

from .errors import BusConfigError, BusTypeError

__all__ = [
    "DEFAULT_CHECKS",
    "Check",
    "CheckRegistry",
    "Severity",
    "check_address_range",
    "check_signal_direction",
    "check_signal_type",
    "check_signal_width",
]


class Severity(Enum):
    """Severity assigned to a registered check."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Check:
    """A named check wrapper with severity and an enable flag."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        severity: Severity = Severity.ERROR,
        enabled: bool = True,
        description: str = "",
    ) -> None:
        self.name = name
        self.func = func
        self.severity = severity
        self.enabled = bool(enabled)
        self.description = description

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if not self.enabled:
            return None
        return self.func(*args, **kwargs)

    def __repr__(self) -> str:
        return (
            f"Check({self.name!r}, severity={self.severity!r}, "
            f"enabled={self.enabled!r})"
        )


class CheckRegistry:
    """A registry of named checks with global and per-check control."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled)
        self._checks: dict[str, Check] = {}

    def register(self, check: Check, overwrite: bool = False) -> Check:
        """Register a :class:`Check`, raising on a duplicate name."""
        if not isinstance(check, Check):
            raise BusConfigError(f"expected a Check, got {type(check).__name__!r}")
        if check.name in self._checks and not overwrite:
            raise BusConfigError(f"check {check.name!r} already registered")
        self._checks[check.name] = check
        return check

    def unregister(self, name: str) -> Check | None:
        """Remove a check if present; return it (or ``None``)."""
        return self._checks.pop(name, None)

    def get(self, name: str) -> Check:
        try:
            return self._checks[name]
        except KeyError:
            raise BusConfigError(f"unknown check {name!r}")

    def enable(self, name: str | None = None) -> None:
        """Enable all checks, or a single check by *name*."""
        if name is None:
            self.enabled = True
        else:
            self.get(name).enabled = True

    def disable(self, name: str | None = None) -> None:
        """Disable all checks, or a single check by *name*."""
        if name is None:
            self.enabled = False
        else:
            self.get(name).enabled = False

    def run(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Run the named check, honouring the global and per-check flags."""
        if not self.enabled:
            return None
        return self.get(name)(*args, **kwargs)

    def names(self) -> list[str]:
        return sorted(self._checks)

    def __contains__(self, name: str) -> bool:
        return name in self._checks

    def __iter__(self) -> Iterator[Check]:
        for name in self.names():
            yield self._checks[name]

    def __len__(self) -> int:
        return len(self._checks)


def check_signal_type(sig: object, name: str, kind: str = "bool") -> SignalType:
    """Check that *sig* is a MyHDL signal of the expected value type.

    Args:
        sig: object to check.
        name: name used in the error message.
        kind: ``"bool"`` (single-bit control) or ``"intbv"`` (bus).
    """
    if not isinstance(sig, SignalType):
        raise BusTypeError(
            f"{name}: expected a MyHDL signal, got {type(sig).__name__!r}"
        )
    if kind == "bool":
        if not isinstance(sig.val, bool):
            raise BusTypeError(
                f"{name}: expected Signal(bool), got Signal({type(sig.val).__name__})"
            )
    elif kind == "intbv":
        if not isinstance(sig.val, intbv):
            raise BusTypeError(
                f"{name}: expected Signal(intbv), got Signal({type(sig.val).__name__})"
            )
    else:
        raise BusConfigError(f"unknown signal kind {kind!r}")
    return sig


def check_signal_width(sig: object, name: str, width: int) -> SignalType:
    """Check that an ``intbv`` signal has exactly *width* bits."""
    check_signal_type(sig, name, kind="intbv")
    actual = len(sig.val)
    if actual != width:
        raise BusTypeError(f"{name}: expected {width}-bit signal, got {actual} bits")
    return sig


_DIRECTIONS = {
    "in": "i",
    "i": "i",
    "input": "i",
    "out": "o",
    "o": "o",
    "output": "o",
}


def check_signal_direction(obj: object, name: str, direction: str) -> SignalType | None:
    """Check that *obj* exposes the directional signal ``name_<i|o>``.

    This is the bus-agnostic form of the ``_i``/``_o`` alias convention
    (``CB-FR-023``): *obj* is typically a view, *direction* is ``"in"`` /
    ``"out"`` (or ``"i"`` / ``"o"``).
    """
    try:
        suffix = _DIRECTIONS[direction]
    except KeyError:
        raise BusConfigError(f"unknown direction {direction!r}")
    attr = f"{name}_{suffix}"
    if not hasattr(obj, attr):
        raise BusTypeError(
            f"{name}: expected a {direction!r} directional signal {attr!r}"
        )
    sig = getattr(obj, attr)
    if sig is not None and not isinstance(sig, SignalType):
        raise BusTypeError(
            f"{name}: {attr!r} is not a MyHDL signal, got {type(sig).__name__!r}"
        )
    return sig


def check_address_range(
    base: int, size: int | None, adr_width: int, name: str = "slave"
) -> int:
    """Check that a slave address window fits and is well-formed."""
    if not isinstance(base, int) or isinstance(base, bool):
        raise BusConfigError(f"{name}: base must be an int, got {base!r}")
    if base < 0:
        raise BusConfigError(f"{name}: base must be >= 0")
    if size is None:
        raise BusConfigError(f"{name}: size is required")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise BusConfigError(f"{name}: size must be > 0")
    if base + size > (1 << adr_width):
        raise BusConfigError(
            f"{name}: window [0x{base:X}, 0x{base + size:X}) exceeds "
            f"the {adr_width}-bit address space"
        )
    return base


#: Default registry holding the four common elaboration-time checks.
DEFAULT_CHECKS = CheckRegistry()
DEFAULT_CHECKS.register(Check("signal_type", check_signal_type))
DEFAULT_CHECKS.register(Check("signal_width", check_signal_width))
DEFAULT_CHECKS.register(Check("signal_direction", check_signal_direction))
DEFAULT_CHECKS.register(Check("address_range", check_address_range))
