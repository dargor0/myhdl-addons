"""Generic, passive signal views shared by every sub-package.

A :class:`SignalView` is a :class:`types.SimpleNamespace` — an ordered bag of
named attributes — used to hold the signals of a component or a bus endpoint.
It **adopts** caller-provided signals (so an enclosing block owns its wires)
and adds a small mapping-style facade plus a ``connect`` copy-wiring helper.
It is deliberately protocol-agnostic, so it can be reused by the component
library, the bus libraries and ad-hoc designs.

Two properties are worth stating explicitly:

* **A view is mutable.**  Members may be rebound, added or deleted after
  construction (``view.y = other_signal``, ``del view.y``); views are therefore
  *not* usable as dict keys/set members.  Mutating a view only rebinds a name
  to a signal; signal *values* are still updated with ``sig.next`` as usual.
* **A view only ever contains signals.**  Every member must be a
  :class:`myhdl.SignalType` or a ``list``/``tuple`` of them; anything else
  raises :class:`~myhdl_addons.common.errors.HdlTypeError`.  Sequence members
  are stored as tuples, so the member set cannot be corrupted after the fact.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any

from myhdl import SignalType, block, instance

from .errors import HdlConfigError, HdlTypeError

__all__ = ["SignalView", "connect"]


def _validated(name: str, value: Any) -> Any:
    """Return *value* if it is a signal or a sequence of signals, else raise."""
    if isinstance(value, SignalType):
        return value
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            if not isinstance(item, SignalType):
                raise HdlTypeError(
                    f"SignalView member {name!r}[{index}] must be a SignalType, "
                    f"got {type(item).__name__!r}"
                )
        return tuple(value)
    raise HdlTypeError(
        f"SignalView member {name!r} must be a SignalType or a list/tuple of "
        f"SignalType, got {type(value).__name__!r}"
    )


class SignalView(SimpleNamespace):
    """A mutable, named collection of signals.

    Built on :class:`types.SimpleNamespace`, so members are plain attributes:
    ``SignalView(a=..., y=...)`` exposes ``view.a`` and ``view["a"]``.  The
    order of the keyword arguments is preserved (CPython dict semantics).
    Every member is validated to be a :class:`~myhdl.SignalType`, or a list or
    tuple of them (stored as a tuple); other values raise ``HdlTypeError``.
    """

    def __init__(self, **signals: Any) -> None:
        for name, value in signals.items():
            self._set_member(name, value)

    def __setattr__(self, name: str, value: Any) -> None:
        self._set_member(name, value)

    def _set_member(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, _validated(name, value))

    @property
    def signals(self) -> dict[str, Any]:
        """Return a copy of the ``name -> signal(s)`` mapping."""
        return dict(vars(self))

    @property
    def names(self) -> list[str]:
        """Return the member names in declaration order."""
        return list(vars(self))

    def __getitem__(self, name: str) -> Any:
        try:
            return getattr(self, name)
        except AttributeError:
            raise KeyError(name) from None

    def __contains__(self, name: str) -> bool:
        return name in vars(self)

    def __iter__(self):
        return iter(vars(self))

    def __len__(self) -> int:
        return len(vars(self))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(vars(self))})"

    def connect(self, src: SignalView, names: Sequence[str] | None = None):
        """Return a ``@block`` wiring matching members of *src* into this view."""
        return connect(src, self, names)


def _iter_pairs(src: SignalView, dst: SignalView, names: Sequence[str] | None):
    for name in names if names is not None else dst.names:
        if name not in src:
            continue
        s = src[name]
        d = dst[name]
        if isinstance(s, (list, tuple)) and isinstance(d, (list, tuple)):
            if len(s) != len(d):
                raise HdlConfigError(
                    f"connect: length mismatch for port {name!r} ({len(s)} vs {len(d)})"
                )
            yield from zip(s, d)
        else:
            yield s, d


@block
def connect(src: SignalView, dst: SignalView, names: Sequence[str] | None = None):
    """Copy-wire matching signals from *src* to *dst* (``dst <- src``)."""
    pairs = list(_iter_pairs(src, dst, names))
    if not pairs:
        raise HdlConfigError("connect: no matching signals between views")

    seen: set[int] = set()
    sensitivity: list[Any] = []
    for s, _ in pairs:
        if id(s) not in seen:
            seen.add(id(s))
            sensitivity.append(s)
    waiter = sensitivity[0] if len(sensitivity) == 1 else tuple(sensitivity)

    @instance
    def logic():
        # initial evaluation at time 0, then on every source change
        while True:
            for s, d in pairs:
                d.next = s
            yield waiter

    return logic
