"""Elaboration-time parameter validation and the preset registry.

Implements ``CB-FR-011`` (validation helpers reused by every per-bus library)
and ``CB-FR-012`` (a named preset registry that per-bus libraries extend with
protocol defaults).  The generic validators are shared via
:mod:`myhdl_addons.common.config`; here they are bound to ``BusConfigError``
so the bus layer keeps raising its own error type.
"""

from typing import Any

from ..common.config import (
    check_alignment as _check_alignment,
)
from ..common.config import (
    check_multiple_of as _check_multiple_of,
)
from ..common.config import (
    check_positive as _check_positive,
)
from ..common.config import (
    check_power_of_two as _check_power_of_two,
)
from ..common.config import (
    check_range as _check_range,
)
from .errors import BusConfigError

__all__ = [
    "check_alignment",
    "check_multiple_of",
    "check_positive_int",
    "check_power_of_two",
    "check_range",
    "get_preset",
    "list_presets",
    "register_preset",
]

_PRESETS: dict[str, dict[str, Any]] = {}


def check_positive_int(value: int, name: str = "value") -> int:
    """Return *value* if it is a positive ``int``, else raise ``BusConfigError``."""
    return _check_positive(value, name, exc=BusConfigError)


def check_power_of_two(value: int, name: str = "value") -> int:
    """Return *value* if it is a positive power of two, else raise."""
    return _check_power_of_two(value, name, exc=BusConfigError)


def check_multiple_of(value: int, multiple: int, name: str = "value") -> int:
    """Return *value* if it is an exact multiple of *multiple*, else raise."""
    return _check_multiple_of(value, multiple, name, exc=BusConfigError)


def check_range(value: int, low: int, high: int, name: str = "value") -> int:
    """Return *value* if ``low <= value < high``, else raise."""
    return _check_range(value, low, high, name, exc=BusConfigError)


def check_alignment(value: int, alignment: int, name: str = "value") -> int:
    """Return *value* if it is aligned to *alignment* (a power-free multiple)."""
    return _check_alignment(value, alignment, name, exc=BusConfigError)


def register_preset(
    name: str, params: dict[str, Any], *, overwrite: bool = False
) -> str:
    """Register a named parameter preset.

    Args:
        name: non-empty preset name.
        params: mapping of parameter names to defaults (copied).
        overwrite: allow replacing an existing preset.
    """
    if not isinstance(name, str) or not name:
        raise BusConfigError("preset name must be a non-empty string")
    if not isinstance(params, dict):
        raise BusConfigError(f"preset {name!r} params must be a dict")
    if name in _PRESETS and not overwrite:
        raise BusConfigError(f"preset {name!r} is already registered")
    _PRESETS[name] = dict(params)
    return name


def get_preset(name: str) -> dict[str, Any]:
    """Return a copy of the named preset, raising if it is unknown."""
    try:
        return dict(_PRESETS[name])
    except KeyError:
        raise BusConfigError(f"unknown preset {name!r}")


def list_presets() -> list[str]:
    """Return the sorted names of every registered preset."""
    return sorted(_PRESETS)
