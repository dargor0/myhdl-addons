"""Simulation-only debugging hooks for the Wishbone library.

Implements ``WB-FR-130`` (requested-signal callback), ``WB-FR-131``
(transaction callback), ``WB-FR-139`` (error / contention callback),
``WB-FR-132`` (multiple subscribers, filtering, enable/disable),
``WB-FR-133`` (integration with BFM/checkers) and ``WB-FR-135``
(simulation-only / non-convertible).

Nothing in this module is convertible to RTL; it exists purely to help
debug designs in the MyHDL Python simulator.
"""

from collections.abc import Callable
from typing import Any

from myhdl import SignalType, block, instance, now

__all__ = ["ContentionEvent", "ErrorEvent", "Trace", "TransactionRecord"]


class TransactionRecord:
    """A single bus transaction observation."""

    __slots__ = (
        "address",
        "end",
        "latency",
        "port",
        "read_data",
        "response",
        "sel",
        "start",
        "we",
        "write_data",
    )

    def __init__(
        self,
        port: str | None = None,
        address: int | None = None,
        we: bool | None = None,
        sel: int | None = None,
    ) -> None:
        self.start: int | None = None
        self.end: int | None = None
        self.port = port
        self.address = address
        self.we = we
        self.sel = sel
        self.write_data: int | None = None
        self.read_data: int | None = None
        self.response: str | None = None  # "ack" | "err" | "rty"
        self.latency: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    def __repr__(self) -> str:
        return (
            f"TransactionRecord(port={self.port!r}, "
            f"address={self.address or 0:#x}, we={self.we!r}, "
            f"response={self.response!r}, latency={self.latency!r})"
        )


class ErrorEvent:
    """A bus error / retry observation."""

    __slots__ = ("address", "kind", "port", "time")

    def __init__(
        self,
        port: str | None = None,
        address: int | None = None,
        kind: str = "err",
    ) -> None:
        self.time: int | None = None
        self.port = port
        self.address = address
        self.kind = kind  # "err" | "rty"


class ContentionEvent:
    """A contention observation (multiple drivers / grants)."""

    __slots__ = ("detail", "time")

    def __init__(self, detail: str = "") -> None:
        self.time: int | None = None
        self.detail = detail


class Trace:
    """A registry of simulation-only hooks (subscribers)."""

    def __init__(self, enabled: bool = False, bus: Any = None, level: int = 1) -> None:
        self.enabled = bool(enabled)
        self.bus = bus
        self.level = level
        self._signals: list[tuple[str, SignalType, Callable[..., None] | None]] = []
        self._transactions: list[Callable[..., None]] = []
        self._errors: list[Callable[..., None]] = []
        self._contentions: list[Callable[..., None]] = []

    # -- registration ------------------------------------------------------
    def signal(
        self,
        sig: SignalType,
        name: str | None = None,
        callback: Callable[..., None] | None = None,
    ) -> SignalType:
        """Register a requested-signal callback.

        The callback is invoked as ``callback(name, old, new, time)``
        whenever *sig* changes value.
        """
        self._signals.append((name or getattr(sig, "_name", "sig"), sig, callback))
        return sig

    def transaction(self, callback: Callable[..., None]) -> None:
        """Register a transaction callback ``callback(record)``."""
        self._transactions.append(callback)

    def error(self, callback: Callable[..., None]) -> None:
        """Register an error/retry callback ``callback(event)``."""
        self._errors.append(callback)

    def contention(self, callback: Callable[..., None]) -> None:
        """Register a contention callback ``callback(event)``."""
        self._contentions.append(callback)

    # -- emission (called by BFM / checkers) -------------------------------
    def emit_transaction(self, record: TransactionRecord) -> None:
        if not self.enabled:
            return
        for cb in self._transactions:
            cb(record)

    def emit_error(self, event: ErrorEvent) -> None:
        if not self.enabled:
            return
        event.time = now()
        for cb in self._errors:
            cb(event)

    def emit_contention(self, event: ContentionEvent) -> None:
        if not self.enabled:
            return
        event.time = now()
        for cb in self._contentions:
            cb(event)

    # -- monitoring --------------------------------------------------------
    @block
    def _watch(
        self,
        name: str,
        sig: SignalType,
        callback: Callable[..., None] | None,
    ):
        @instance
        def watcher():
            prev = sig.val
            while True:
                yield sig
                val = sig.val
                if val != prev:
                    if callback is not None:
                        callback(name, prev, val, now())
                    prev = val

        return watcher

    @block
    def monitors(self):
        """Return the signal-monitor block (simulation only)."""
        if not self.enabled:
            return []
        insts = []
        for name, sig, callback in self._signals:
            insts.append(self._watch(name, sig, callback))
        return insts
