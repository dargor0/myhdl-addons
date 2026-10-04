"""Common transaction / event records and status enumerations.

Implements ``CB-FR-080`` (``TransactionRecord``, ``ErrorEvent`` and
``ContentionEvent`` with ``as_dict()`` serialization), ``CB-FR-081``
(extensible via an ``extra`` mapping and subclassing) and ``CB-FR-082``
(the ``BusStatus`` and ``Direction`` enumerations).
"""

from enum import Enum
from typing import Any

__all__ = [
    "BusStatus",
    "ContentionEvent",
    "Direction",
    "ErrorEvent",
    "TransactionRecord",
    "extend_bus_status",
]


class BusStatus(Enum):
    """Outcome of a bus transaction (common base status)."""

    OK = "ok"
    ERROR = "error"
    RETRY = "retry"
    DENIED = "denied"
    EXOKAY = "exokay"


def extend_bus_status(name: str, members: dict[str, Any] | None = None) -> Any:
    """Build a per-bus status enum that extends the common ``BusStatus``.

    Python's ``enum.Enum`` cannot be subclassed once it has members, so a
    per-bus status is created as a **superset** enum: it keeps every
    ``BusStatus`` member and adds the bus-specific codes.  This satisfies
    ``CB-FR-082`` ("extend the base status") while preserving ``Enum``
    semantics (``.name``/``.value``, iteration, ``as_dict``).
    """
    merged = {m.name: m.value for m in BusStatus}
    if members:
        merged.update(members)
    return Enum(name, merged)


class Direction(Enum):
    """Direction / kind of a bus operation."""

    READ = "read"
    WRITE = "write"
    ATOMIC = "atomic"
    STREAM = "stream"


class _Record:
    """Base for records offering ``as_dict()`` serialization."""

    __slots__ = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a plain, JSON-friendly dict of the record's fields."""
        out: dict[str, Any] = {}
        for name in self.__slots__:
            value = getattr(self, name)
            if isinstance(value, Enum):
                value = value.value
            elif name == "extra" and value:
                value = dict(value)
            out[name] = value
        return out


class TransactionRecord(_Record):
    """A single bus transaction observation (``CB-FR-080``)."""

    __slots__ = (
        "address",
        "data",
        "direction",
        "end",
        "extra",
        "latency",
        "length",
        "port",
        "start",
        "status",
    )

    def __init__(
        self,
        port: str | None = None,
        address: int | None = None,
        direction: Direction = Direction.READ,
        length: int = 1,
        data: Any = None,
        status: BusStatus = BusStatus.OK,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.port = port
        self.address = address
        self.direction = direction
        self.length = length
        self.data = data
        self.status = status
        self.latency: int | None = None
        self.start: int | None = None
        self.end: int | None = None
        self.extra = dict(extra) if extra else {}

    def __repr__(self) -> str:
        return (
            f"TransactionRecord(port={self.port!r}, "
            f"address={self.address!r}, direction={self.direction!r}, "
            f"status={self.status!r}, latency={self.latency!r})"
        )


class ErrorEvent(_Record):
    """A bus error / retry observation (``CB-FR-080``)."""

    __slots__ = ("address", "extra", "kind", "port", "time")

    def __init__(
        self,
        port: str | None = None,
        address: int | None = None,
        kind: str = "error",
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.time: int | None = None
        self.port = port
        self.address = address
        self.kind = kind
        self.extra = dict(extra) if extra else {}

    def __repr__(self) -> str:
        return (
            f"ErrorEvent(port={self.port!r}, address={self.address!r}, "
            f"kind={self.kind!r})"
        )


class ContentionEvent(_Record):
    """A contention observation (multiple drivers / grants, ``CB-FR-080``)."""

    __slots__ = ("detail", "extra", "port", "time")

    def __init__(
        self,
        detail: str = "",
        port: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.time: int | None = None
        self.port = port
        self.detail = detail
        self.extra = dict(extra) if extra else {}

    def __repr__(self) -> str:
        return f"ContentionEvent(port={self.port!r}, detail={self.detail!r})"
