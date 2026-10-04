"""Simulation-only hook registry.

Implements ``CB-FR-110`` (requested-signal, transaction and
error/contention callbacks with multiple subscribers and per-port
filtering), ``CB-FR-111`` (global and per-hook enable/disable, inert when
disabled) and ``CB-FR-113`` (shared by BFMs and checkers).

Nothing here is convertible to RTL; it exists purely to debug designs in
the MyHDL Python simulator.
"""

from collections.abc import Callable
from typing import Any

from myhdl import SignalType, block, instance, now

__all__ = ["Trace"]


class _Hook:
    """A single registered callback with its filtering/enable state."""

    __slots__ = ("callback", "enabled", "name", "port")

    def __init__(
        self,
        callback: Callable[..., None] | None,
        port: str | None = None,
        name: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.callback = callback
        self.port = port
        self.name = name
        self.enabled = bool(enabled)


class Trace:
    """A registry of simulation-only hooks (subscribers)."""

    def __init__(self, enabled: bool = False, bus: Any = None, level: int = 1) -> None:
        self.enabled = bool(enabled)
        self.bus = bus
        self.level = level
        self._signals: list[tuple[_Hook, SignalType]] = []
        self._transactions: list[_Hook] = []
        self._errors: list[_Hook] = []
        self._contentions: list[_Hook] = []

    # -- global / per-hook enable ------------------------------------------
    def enable(self, name: str | None = None) -> None:
        """Enable tracing globally, or re-enable the hook called *name*."""
        if name is None:
            self.enabled = True
        else:
            self._find(name).enabled = True

    def disable(self, name: str | None = None) -> None:
        """Disable tracing globally, or disable the hook called *name*."""
        if name is None:
            self.enabled = False
        else:
            self._find(name).enabled = False

    def _find(self, name: str) -> _Hook:
        for hook in self._hooks():
            if hook.name == name:
                return hook
        for hook, sig in self._signals:
            if getattr(sig, "_name", None) == name or hook.name == name:
                return hook
        return _Hook(None, name=name)

    def _hooks(self) -> list[_Hook]:
        return list(self._transactions) + list(self._errors) + list(self._contentions)

    # -- registration ------------------------------------------------------
    def signal(
        self,
        sig: SignalType,
        name: str | None = None,
        callback: Callable[..., None] | None = None,
        port: str | None = None,
    ) -> SignalType:
        """Register a requested-signal callback.

        The callback is invoked as ``callback(name, old, new, time)``
        whenever *sig* changes.  Returns *sig* (for convenient chaining).
        """
        hook = _Hook(callback, port=port, name=name or getattr(sig, "_name", "sig"))
        self._signals.append((hook, sig))
        return sig

    def transaction(
        self,
        callback: Callable[..., None],
        port: str | None = None,
        name: str | None = None,
    ) -> _Hook:
        """Register a transaction callback ``callback(record)``."""
        hook = _Hook(callback, port=port, name=name or "transaction")
        self._transactions.append(hook)
        return hook

    def error(
        self,
        callback: Callable[..., None],
        port: str | None = None,
        name: str | None = None,
    ) -> _Hook:
        """Register an error/retry callback ``callback(event)``."""
        hook = _Hook(callback, port=port, name=name or "error")
        self._errors.append(hook)
        return hook

    def contention(
        self,
        callback: Callable[..., None],
        port: str | None = None,
        name: str | None = None,
    ) -> _Hook:
        """Register a contention callback ``callback(event)``."""
        hook = _Hook(callback, port=port, name=name or "contention")
        self._contentions.append(hook)
        return hook

    # -- emission (called by BFM / checkers) -------------------------------
    def _emit(self, hooks: list[_Hook], event: Any) -> None:
        if not self.enabled:
            return
        for hook in hooks:
            if not hook.enabled:
                continue
            if hook.port is not None and hook.port != getattr(event, "port", None):
                continue
            if hook.callback is not None:
                hook.callback(event)

    def emit_transaction(self, record: Any) -> None:
        self._emit(self._transactions, record)

    def emit_error(self, event: Any) -> None:
        if event.time is None:
            event.time = now()
        self._emit(self._errors, event)

    def emit_contention(self, event: Any) -> None:
        if event.time is None:
            event.time = now()
        self._emit(self._contentions, event)

    # -- monitoring --------------------------------------------------------
    @block
    def _watch(self, hook: _Hook, sig: SignalType):
        @instance
        def watcher():
            prev = sig.val
            while True:
                yield sig
                val = sig.val
                if val != prev:
                    if hook.callback is not None and hook.enabled and self.enabled:
                        hook.callback(hook.name, prev, val, now())
                    prev = val

        return watcher

    @block
    def monitors(self):
        """Return the signal-monitor block (simulation only)."""
        if not self.enabled:
            return []
        insts = []
        for hook, sig in self._signals:
            if hook.enabled:
                insts.append(self._watch(hook, sig))
        return insts
