"""AXI bus-functional models (simulation only, ``AX-FR-090/091/093``)."""

from __future__ import annotations

from typing import Any

from myhdl import now

from ..bus_common import Direction, ErrorEvent, Trace, TransactionRecord
from .checks import AxiError
from .status import AxiStatus, resp_to_status

__all__ = ["AxiBFM", "AxiLiteBFM"]

_ERROR_STATUS = (AxiStatus.SLVERR, AxiStatus.DECERR)


class AxiBFM:
    """Drive an AXI4 (full) :class:`AxiMasterView` with INCR bursts."""

    def __init__(
        self, port: Any, timeout: int = 1000, trace: Trace | None = None, id: int = 0
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.trace = trace
        self.id_value = id
        self.last_data: list[int] | None = None
        self.last_resp = AxiStatus.OKAY
        self.last_error = False
        self.last_latency: int | None = None
        self.last_bid: int | None = None
        self.last_rid: int | None = None
        self.last_outstanding: dict[int, list[int]] | None = None
        self._bytes = len(port.wdata) // 8
        self._size_enc = self._bytes.bit_length() - 1
        self._all_strb = (1 << self._bytes) - 1

    def _record(
        self, addr: int, direction: Direction, length: int
    ) -> TransactionRecord:
        rec = TransactionRecord(
            port=self.port.name,
            address=int(addr),
            direction=direction,
            length=length,
        )
        rec.start = now()
        return rec

    def write(self, addr: int, data: Any, burst: int = 1) -> Any:
        """Write a burst; ``data`` is an iterable of beats, ``burst`` an AxBURST code."""
        p = self.port
        beats = list(data)
        rec = self._record(addr, Direction.WRITE, len(beats))
        p.awaddr.next = addr
        p.awlen.next = len(beats) - 1
        p.awsize.next = self._size_enc
        p.awburst.next = burst
        p.awid.next = self.id_value
        p.awlock.next = 0
        p.awcache.next = 0
        p.awprot.next = 0
        p.awvalid.next = 1
        cycles = 0
        while not p.awready:
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                raise AxiError(f"write AW timeout at {addr:#x}")
        yield p.aclk.posedge
        p.awvalid.next = 0
        last = len(beats) - 1
        # stream the W beats, holding WVALID high (one beat per clock)
        for i, beat in enumerate(beats):
            p.wdata.next = beat
            p.wstrb.next = self._all_strb
            p.wlast.next = 1 if i == last else 0
            p.wvalid.next = 1
            yield p.aclk.posedge
        p.wvalid.next = 0
        cycles = 0
        while not p.bvalid:
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                raise AxiError(f"write B timeout at {addr:#x}")
        self.last_bid = int(p.bid)
        self._bresp = int(p.bresp)
        p.bready.next = 1
        yield p.aclk.posedge
        p.bready.next = 0
        status = resp_to_status(self._bresp)
        rec.end = now()
        rec.latency = cycles + 1
        rec.status = status
        self.last_resp = status
        self.last_error = status in _ERROR_STATUS
        self._emit(rec)

    def read(self, addr: int, length: int = 1, burst: int = 1) -> Any:
        """Read a burst; the beats are stored in ``last_data``."""
        p = self.port
        rec = self._record(addr, Direction.READ, length)
        p.araddr.next = addr
        p.arlen.next = length - 1
        p.arsize.next = self._size_enc
        p.arburst.next = burst
        p.arid.next = self.id_value
        p.arlock.next = 0
        p.arcache.next = 0
        p.arprot.next = 0
        p.arvalid.next = 1
        p.rready.next = 1  # assert early and hold for the whole burst
        cycles = 0
        while not p.arready:
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                raise AxiError(f"read AR timeout at {addr:#x}")
        yield p.aclk.posedge
        p.arvalid.next = 0
        out = []
        status = AxiStatus.OKAY
        for _ in range(length):
            cycles = 0
            while not p.rvalid:
                yield p.aclk.posedge
                cycles += 1
                if cycles > self.timeout:
                    raise AxiError(f"read R timeout at {addr:#x}")
            out.append(int(p.rdata))
            self.last_rid = int(p.rid)
            self._rresp = int(p.rresp)
            yield p.aclk.posedge
        p.rready.next = 0
        status = resp_to_status(self._rresp)
        self.last_data = out
        self.last_resp = status
        self.last_error = status in _ERROR_STATUS
        rec.data = out
        rec.end = now()
        rec.latency = cycles + 1
        rec.status = status
        self._emit(rec)

    def _emit(self, rec: TransactionRecord) -> None:
        if self.trace is None:
            return
        self.trace.emit_transaction(rec)
        if self.last_error:
            self.trace.emit_error(
                ErrorEvent(port=rec.port, address=rec.address, kind=rec.status.value)
            )

    def read_outstanding(self, requests: Any) -> Any:
        """Issue several outstanding reads and group completions by ID.

        *requests* is an iterable of ``(addr, length, id)``.  Requires a slave
        that supports outstanding reads (e.g.
        :func:`myhdl_addons.axi.axi_full_slave_oo`); the number of requests must
        not exceed the slave's queue depth.  The per-ID beat lists are stored in
        ``last_outstanding``.
        """
        p = self.port
        reqs = list(requests)
        p.rready.next = 0
        for addr, length, tid in reqs:
            p.araddr.next = addr
            p.arlen.next = length - 1
            p.arsize.next = self._size_enc
            p.arburst.next = 1
            p.arid.next = tid
            p.arvalid.next = 1
            cycles = 0
            while not p.arready:
                yield p.aclk.posedge
                cycles += 1
                if cycles > self.timeout:
                    raise AxiError(f"outstanding AR timeout at {addr:#x}")
            yield p.aclk.posedge
            p.arvalid.next = 0
        p.rready.next = 0
        yield p.aclk.negedge
        got: dict[int, list[int]] = {}
        total = sum(length for _, length, _ in reqs)
        for _ in range(total):
            cycles = 0
            while not p.rvalid:
                yield p.aclk.negedge
                cycles += 1
                if cycles > self.timeout:
                    raise AxiError("outstanding R timeout")
            # sample mid-cycle (away from the posedge that advances the slave)
            got.setdefault(int(p.rid), []).append(int(p.rdata))
            p.rready.next = 1
            yield p.aclk.posedge
            p.rready.next = 0
            yield p.aclk.negedge
        self.last_outstanding = got


class AxiLiteBFM:
    """Drive an AXI4-Lite :class:`AxiMasterView` from a testbench."""

    def __init__(
        self, port: Any, timeout: int = 1000, trace: Trace | None = None
    ) -> None:
        self.port = port
        self.timeout = timeout
        self.trace = trace
        self.last_data: int | None = None
        self.last_resp = AxiStatus.OKAY
        self.last_error = False
        self.last_latency: int | None = None

    def _all_strb(self) -> int:
        return (1 << len(self.port.wstrb)) - 1

    def _record(
        self, addr: int, direction: Direction, data: Any = None
    ) -> TransactionRecord:
        rec = TransactionRecord(
            port=self.port.name,
            address=int(addr),
            direction=direction,
            data=None if data is None else int(data),
        )
        rec.start = now()
        return rec

    def _emit(self, rec: TransactionRecord) -> None:
        if self.trace is None:
            return
        self.trace.emit_transaction(rec)
        if self.last_error:
            self.trace.emit_error(
                ErrorEvent(port=rec.port, address=rec.address, kind=rec.status.value)
            )

    def _finish(self, rec: TransactionRecord, status: AxiStatus) -> None:
        rec.end = now()
        rec.status = status
        self.last_resp = status
        self.last_error = status in _ERROR_STATUS

    # -- transactions ------------------------------------------------------
    def write(self, addr: int, data: int, strb: int | None = None) -> Any:
        """Perform an AXI4-Lite write; ``yield`` this generator."""
        p = self.port
        if strb is None:
            strb = self._all_strb()
        rec = self._record(addr, Direction.WRITE, data=data)
        p.awaddr.next = addr
        p.awprot.next = 0
        p.awvalid.next = 1
        p.wdata.next = data
        p.wstrb.next = strb
        p.wvalid.next = 1
        cycles = 0
        while not (p.awready and p.wready):
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                self._finish(rec, AxiStatus.DECERR)
                raise AxiError(f"write address timeout at {addr:#x}")
        # both READY high: the transfer completes on the next rising edge
        yield p.aclk.posedge
        p.awvalid.next = 0
        p.wvalid.next = 0
        cycles = 0
        while not p.bvalid:
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                raise AxiError(f"write response timeout at {addr:#x}")
        p.bready.next = 1
        yield p.aclk.posedge
        p.bready.next = 0
        self.last_latency = cycles + 1
        rec.latency = self.last_latency
        self._finish(rec, resp_to_status(p.bresp))
        self._emit(rec)

    def read(self, addr: int) -> Any:
        """Perform an AXI4-Lite read; result stored in ``last_data``."""
        p = self.port
        rec = self._record(addr, Direction.READ)
        p.araddr.next = addr
        p.arprot.next = 0
        p.arvalid.next = 1
        cycles = 0
        while not p.arready:
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                raise AxiError(f"read address timeout at {addr:#x}")
        # ARREADY high: the address transfer completes on the next rising edge
        yield p.aclk.posedge
        p.arvalid.next = 0
        cycles = 0
        while not p.rvalid:
            yield p.aclk.posedge
            cycles += 1
            if cycles > self.timeout:
                raise AxiError(f"read response timeout at {addr:#x}")
        p.rready.next = 1
        yield p.aclk.posedge
        p.rready.next = 0
        self.last_data = int(p.rdata)
        self.last_latency = cycles + 1
        rec.data = self.last_data
        rec.latency = self.last_latency
        self._finish(rec, resp_to_status(p.rresp))
        self._emit(rec)

    def rmw(self, addr: int, mask: int, data: int, strb: int | None = None) -> Any:
        """Read-modify-write; the read result is stored in ``last_data``."""
        yield self.read(addr)
        current = self.last_data or 0
        yield self.write(addr, (current & ~mask) | (data & mask), strb=strb)
