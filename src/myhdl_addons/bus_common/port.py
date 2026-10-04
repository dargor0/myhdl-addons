"""Port and directional-view base classes.

Implements ``CB-FR-020`` (``PortBase`` holds an endpoint's signals and
``ViewBase`` exposes directional aliases and geometry), ``CB-FR-022``
(canonical ``.clk`` / ``.rst`` accessors) and ``CB-FR-023`` (the uniform
``_o``/``_i`` directional-alias convention).
"""

from collections.abc import Iterator
from typing import Any

from myhdl import SignalType

from .errors import BusConfigError

__all__ = ["PortBase", "ViewBase"]

_DIRECTION_SUFFIX = {
    "in": "i",
    "i": "i",
    "input": "i",
    "out": "o",
    "o": "o",
    "output": "o",
}


class PortBase:
    """The raw signal set of one bus endpoint.

    Subclasses (per bus) create their protocol-specific signals and register
    them with :meth:`add`; geometry is carried as keyword metadata.
    """

    def __init__(
        self,
        name: str | None = None,
        clk: SignalType | None = None,
        rst: SignalType | None = None,
        **geometry: Any,
    ) -> None:
        self.name = name
        self.clk = clk
        self.rst = rst
        self._signals: dict[str, SignalType] = {}
        self._geometry: dict[str, Any] = dict(geometry)

    def add(self, name: str, sig: SignalType) -> SignalType:
        """Register a signal under *name* and return it."""
        self._signals[name] = sig
        return sig

    def signal(self, name: str, default: Any = None) -> Any:
        return self._signals.get(name, default)

    @property
    def signals(self) -> dict[str, SignalType]:
        return dict(self._signals)

    @property
    def geometry(self) -> dict[str, Any]:
        return dict(self._geometry)

    def __getitem__(self, name: str) -> Any:
        return self._signals[name]

    def __contains__(self, name: str) -> bool:
        return name in self._signals

    def __iter__(self) -> Iterator[str]:
        return iter(self._signals)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class ViewBase:
    """A directional view over a :class:`PortBase`.

    Subclasses bind their directional names through :meth:`alias` /
    :meth:`alias_direction`.  The owning clock and reset are exposed through
    the canonical ``.clk`` / ``.rst`` accessors (``CB-FR-022``).
    """

    def __init__(
        self,
        port: PortBase,
        clk: SignalType | None = None,
        rst: SignalType | None = None,
    ) -> None:
        self._port = port
        self.name = getattr(port, "name", None)
        self._clk = clk if clk is not None else getattr(port, "clk", None)
        self._rst = rst if rst is not None else getattr(port, "rst", None)

    @property
    def clk(self) -> SignalType | None:
        return self._clk

    @clk.setter
    def clk(self, value: SignalType | None) -> None:
        self._clk = value

    @property
    def rst(self) -> SignalType | None:
        return self._rst

    @rst.setter
    def rst(self, value: SignalType | None) -> None:
        self._rst = value

    @property
    def port(self) -> PortBase:
        return self._port

    @property
    def geometry(self) -> dict[str, Any]:
        return self._port.geometry

    def _source(self, src: str) -> Any:
        if hasattr(self._port, src):
            return getattr(self._port, src)
        return self._port.signal(src)

    def alias(self, dst: str, src: str, default: Any = None) -> Any:
        """Expose ``port.<src>`` as ``view.<dst>`` (``None`` when absent)."""
        value = self._source(src)
        if value is None:
            value = default
        setattr(self, dst, value)
        return value

    def alias_direction(self, base: str, direction: str, src: str) -> Any:
        """Expose ``port.<src>`` as ``view.<base>_<i|o>``."""
        try:
            suffix = _DIRECTION_SUFFIX[direction]
        except KeyError:
            raise BusConfigError(f"unknown direction {direction!r}")
        return self.alias(f"{base}_{suffix}", src)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"
