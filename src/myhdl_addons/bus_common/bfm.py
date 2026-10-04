"""Bus-functional-model base classes (simulation only).

Implements ``CB-FR-090`` (``BFMBase`` with configurable timeout, error
handling, trace emission and the ``read`` / ``write`` / ``rmw`` accessor
pattern), ``CB-FR-091`` (transaction/error events fed to the common
``Trace``; non-convertible) and ``CB-FR-093`` (``StreamBFMBase`` for
packet/stream buses).
"""

from collections.abc import Sequence
from typing import Any

from myhdl import now

from .records import BusStatus, Direction, ErrorEvent, TransactionRecord
from .trace import Trace

__all__ = ["BFMBase", "StreamBFMBase"]


class BFMBase:
    """Base class for address-mapped bus-functional models.

    Per-bus BFMs subclass this and implement :meth:`drive`,
    :meth:`wait_response` (a generator) and optionally :meth:`release`.
    """

    def __init__(
        self, port: Any, timeout: int = 1000, trace: Trace | None = None
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.trace = trace
        self.last_data: Any = None
        self.last_error = False
        self.last_latency: int | None = None
        self.last_status = BusStatus.OK

    # -- to be implemented by per-bus BFMs ---------------------------------
    def drive(self, addr: int, we: bool, data: Any = None, sel: Any = None) -> None:
        """Drive the request signals (non-generator)."""
        raise NotImplementedError

    def wait_response(self) -> Any:
        """Generator: wait for the response, updating ``last_*`` fields."""
        raise NotImplementedError

    def release(self) -> None:
        """Deassert the request signals after a transaction (optional)."""

    # -- helpers -----------------------------------------------------------
    @property
    def port_name(self) -> Any:
        return getattr(self.port, "name", self.port)

    def _emit(self, record: TransactionRecord) -> None:
        if self.trace is None:
            return
        self.trace.emit_transaction(record)
        if self.last_error or record.status is not BusStatus.OK:
            self.trace.emit_error(
                ErrorEvent(
                    port=record.port,
                    address=record.address,
                    kind=record.status.value,
                )
            )

    # -- transactions ------------------------------------------------------
    def access(self, addr: int, we: bool, data: Any = None, sel: Any = None) -> Any:
        """Generic transaction generator; per-bus callers use ``read``/``write``."""
        direction = Direction.WRITE if we else Direction.READ
        record = TransactionRecord(
            port=self.port_name,
            address=int(addr),
            direction=direction,
            data=None if data is None else int(data),
        )
        record.start = now()
        self.last_error = False
        self.drive(addr, we, data, sel)
        yield self.wait_response()
        self.release()
        record.end = now()
        record.latency = self.last_latency
        record.status = self.last_status
        if not we:
            record.data = self.last_data
        self._emit(record)

    def read(self, addr: int, sel: Any = None) -> Any:
        """Perform a read; the result is stored in ``last_data``."""
        return self.access(addr, False, None, sel)

    def write(self, addr: int, data: Any, sel: Any = None) -> Any:
        """Perform a write; ``yield`` this generator."""
        return self.access(addr, True, data, sel)

    def rmw(self, addr: int, mask: int, data: int, sel: Any = None) -> Any:
        """Read-modify-write; the read result is stored in ``last_data``."""
        yield self.read(addr, sel=sel)
        current = self.last_data or 0
        yield self.write(addr, (current & ~mask) | (data & mask), sel=sel)


class StreamBFMBase:
    """Base class for packet/stream buses (e.g. AXI-Stream, ``CB-FR-093``)."""

    def __init__(
        self, port: Any, timeout: int = 1000, trace: Trace | None = None
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.trace = trace
        self.last_data: Any = None
        self.last_error = False

    # -- to be implemented by per-bus BFMs ---------------------------------
    def drive_beat(self, data: Any, last: bool = False) -> None:
        """Drive one beat (non-generator)."""
        raise NotImplementedError

    def wait_beat(self) -> Any:
        """Generator: wait for one beat, updating ``last_data``."""
        raise NotImplementedError

    # -- helpers -----------------------------------------------------------
    @property
    def port_name(self) -> Any:
        return getattr(self.port, "name", self.port)

    # -- transactions ------------------------------------------------------
    def send(self, data: Any, last: bool = False) -> Any:
        """Send one beat; ``yield`` this generator."""
        self.drive_beat(data, last)
        yield self.wait_beat()

    def send_packet(self, beats: Sequence[Any]) -> Any:
        """Send a packet as a sequence of beats, last one flagged."""
        n = len(beats)
        for i, beat in enumerate(beats):
            yield self.send(beat, last=(i == n - 1))

    def recv(self) -> Any:
        """Receive one beat; the result is stored in ``last_data``."""
        yield self.wait_beat()

    def recv_packet(self, length: int) -> Any:
        """Receive *length* beats; the list is stored in ``last_data``."""
        out = []
        for _ in range(length):
            yield self.recv()
            out.append(self.last_data)
        self.last_data = out
