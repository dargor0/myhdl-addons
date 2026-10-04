"""Shared elaboration-time configuration helpers.

Generic, protocol-agnostic validation and introspection helpers reused by
every sub-package:

* parameter validators raising a caller-supplied exception class (so the bus
  layer can keep raising ``BusConfigError`` while components raise
  ``HdlConfigError``);
* :class:`ComponentBase`, the uniform configuration/introspection protocol
  (``as_dict``/``repr``) used by the component library.

This module depends only on :mod:`myhdl_addons.common.errors` and the standard
library.
"""

from collections.abc import Iterable
from typing import Any, ClassVar

from .errors import ErrorType, HdlConfigError

__all__ = [
    "ComponentBase",
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
    "mask",
    "normalize_subset",
]


def check_int(value: object, name: str, *, exc: ErrorType = HdlConfigError) -> int:
    """Return *value* if it is an ``int`` (but not a ``bool``), else raise *exc*."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise exc(f"{name} must be an int, got {value!r}")
    return value


def check_bool(value: object, name: str, *, exc: ErrorType = HdlConfigError) -> bool:
    """Return *value* if it is a ``bool``, else raise *exc*."""
    if not isinstance(value, bool):
        raise exc(f"{name} must be a bool, got {value!r}")
    return value


def check_positive(value: object, name: str, *, exc: ErrorType = HdlConfigError) -> int:
    """Return *value* if it is a positive ``int``, else raise *exc*."""
    check_int(value, name, exc=exc)
    if value <= 0:
        raise exc(f"{name} must be positive, got {value!r}")
    return value


def check_non_negative(
    value: object, name: str, *, exc: ErrorType = HdlConfigError
) -> int:
    """Return *value* if it is a non-negative ``int``, else raise *exc*."""
    check_int(value, name, exc=exc)
    if value < 0:
        raise exc(f"{name} must be non-negative, got {value!r}")
    return value


def check_power_of_two(
    value: object, name: str, *, exc: ErrorType = HdlConfigError
) -> int:
    """Return *value* if it is a positive power of two, else raise *exc*."""
    check_int(value, name, exc=exc)
    if value <= 0 or (value & (value - 1)) != 0:
        raise exc(f"{name} must be a positive power of two, got {value!r}")
    return value


def check_multiple_of(
    value: object, multiple: object, name: str, *, exc: ErrorType = HdlConfigError
) -> int:
    """Return *value* if it is an exact multiple of *multiple*, else raise *exc*."""
    check_int(value, name, exc=exc)
    check_int(multiple, "multiple", exc=exc)
    if multiple <= 0:
        raise exc(f"multiple must be positive, got {multiple!r}")
    if value % multiple != 0:
        raise exc(f"{name} ({value!r}) must be a multiple of {multiple!r}")
    return value


def check_range(
    value: object,
    low: int,
    high: int,
    name: str,
    *,
    exc: ErrorType = HdlConfigError,
) -> int:
    """Return *value* if ``low <= value < high``, else raise *exc*."""
    check_int(value, name, exc=exc)
    if value < low or value >= high:
        raise exc(f"{name} ({value!r}) must be in [{low!r}, {high!r})")
    return value


def check_alignment(
    value: object, alignment: object, name: str, *, exc: ErrorType = HdlConfigError
) -> int:
    """Return *value* if it is aligned to *alignment*, else raise *exc*."""
    check_positive(alignment, "alignment", exc=exc)
    return check_multiple_of(value, alignment, name, exc=exc)


def check_choice(
    value: object,
    allowed: Iterable[Any],
    name: str,
    *,
    exc: ErrorType = HdlConfigError,
) -> Any:
    """Return *value* if it is one of *allowed*, else raise *exc*."""
    allowed = tuple(allowed)
    if value not in allowed:
        raise exc(f"{name} must be one of {allowed}, got {value!r}")
    return value


def check_registered(
    value: object, name: str = "registered", *, exc: ErrorType = HdlConfigError
) -> int:
    """Return *value* if it is ``0`` or ``1``, else raise *exc*."""
    check_int(value, name, exc=exc)
    if value not in (0, 1):
        raise exc(f"{name} must be 0 or 1, got {value!r}")
    return value


def ceil_log2(n: int) -> int:
    """Return ``ceil(log2(n))``, i.e. the bits needed to index ``n`` items.

    ``n <= 1`` yields ``0``; callers that need a physical signal take
    ``max(1, ceil_log2(n))``.
    """
    check_positive(n, "n")
    return (n - 1).bit_length()


def mask(width: int) -> int:
    """Return a *width*-bit all-ones mask."""
    check_positive(width, "width")
    return (1 << width) - 1


def normalize_subset(
    value: object,
    allowed: Iterable[Any],
    name: str,
    *,
    default: Iterable[Any] | None = None,
    names: dict[Any, str] | None = None,
) -> tuple[Any, ...]:
    """Validate and canonicalise a feature subset.

    *value* may be ``None`` (use *default*), a single element, or an iterable
    of elements.  Elements may be the canonical codes or their string names
    (when *names* maps codes to names).  The result is a tuple ordered as in
    *allowed* with duplicates removed.
    """
    allowed = tuple(allowed)
    if names is not None:
        lookup = {code: code for code in allowed}
        lookup.update({label: code for code, label in names.items()})
        lookup.update({label.lower(): code for code, label in names.items()})
    else:
        lookup = {code: code for code in allowed}

    if value is None:
        if default is None:
            raise HdlConfigError(f"{name} must be provided")
        elements = tuple(default)
    elif isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        elements = (value,)
    else:
        elements = tuple(value)
    if not elements:
        raise HdlConfigError(f"{name} must not be empty")

    resolved: list[Any] = []
    for element in elements:
        code = lookup.get(element, lookup.get(str(element).upper()))
        if code is None:
            raise HdlConfigError(f"unknown {name} entry {element!r}")
        resolved.append(code)
    if len(set(resolved)) != len(resolved):
        raise HdlConfigError(f"{name} contains duplicates")
    return tuple(code for code in allowed if code in resolved)


class ComponentBase:
    """Mixin giving a configurable object a uniform configuration protocol.

    Subclasses set ``self._params`` (an ordered mapping of effective
    configuration) after validation.
    """

    _params: ClassVar[dict[str, Any]] = {}

    def as_dict(self) -> dict[str, Any]:
        """Return the effective configuration as a plain ``dict``."""
        return dict(self._params)

    def __repr__(self) -> str:
        inner = ", ".join(f"{k}={v!r}" for k, v in self._params.items())
        return f"{type(self).__name__}({inner})"
