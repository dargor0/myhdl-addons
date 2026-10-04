"""Bus-functional model (simulation-only).

Implements ``WB-FR-080`` (``read``/``write``/``rmw`` accessors usable inside
``@instance`` generators), ``WB-FR-081`` (configurable timeout, error
handling) and ``WB-FR-083`` (simulation-only).  Read results are stored on
``BFM.last_data``; callers use ``yield bfm.read(addr)`` then inspect it.
"""

from typing import Any

from myhdl import now

from .checks import WishboneError
from .interface import MasterView
from .trace import ErrorEvent, Trace, TransactionRecord

__all__ = ["WishboneBFM"]


class WishboneBFM:
    """Drive a :class:`MasterView` from a MyHDL testbench."""

    def __init__(
        self,
        wb: MasterView,
        timeout: int = 1000,
        trace: Trace | None = None,
    ) -> None:
        self.wb = wb
        self.timeout = timeout
        self.trace = trace
        self.last_data: int | None = None
        self.last_error = False

    # -- helpers -----------------------------------------------------------
    def _all_sel(self) -> int:
        return (1 << len(self.wb.sel_o)) - 1

    def _finish(
        self,
        rec: TransactionRecord,
        response: str,
        error: bool = False,
    ) -> Any:
        wb = self.wb
        wb.cyc_o.next = 0
        wb.stb_o.next = 0
        wb.we_o.next = 0
        rec.response = response
        rec.end = now()
        self.last_error = error
        if self.trace is not None:
            self.trace.emit_transaction(rec)
            if error:
                self.trace.emit_error(
                    ErrorEvent(port=wb.name, address=rec.address, kind=response)
                )
        yield wb.clk.posedge

    def _wait(self, rec: TransactionRecord, kind: str) -> Any:
        """Wait for a response, checking ERR first; raise on error/timeout."""
        wb = self.wb
        cycles = 0
        while True:
            if wb.err_i is not None and wb.err_i:
                yield self._finish(rec, "err", error=True)
                raise WishboneError(f"{kind} error at {rec.address:#x}")
            if wb.ack_i:
                break
            yield wb.clk.posedge
            cycles += 1
            if cycles > self.timeout:
                yield self._finish(rec, "timeout", error=True)
                raise WishboneError(f"{kind} timeout at {rec.address:#x}")
        rec.latency = cycles + 1

    # -- transactions ------------------------------------------------------
    def write(self, addr: int, data: int, sel: int | None = None) -> Any:
        """Perform a classic write; ``yield`` this generator."""
        wb = self.wb
        if sel is None:
            sel = self._all_sel()
        rec = TransactionRecord(port=wb.name, address=int(addr), we=True, sel=int(sel))
        rec.start = now()
        rec.write_data = int(data)
        wb.adr_o.next = addr
        wb.dat_o.next = data
        wb.we_o.next = 1
        wb.sel_o.next = sel
        wb.cyc_o.next = 1
        wb.stb_o.next = 1
        yield self._wait(rec, "write")
        yield self._finish(rec, "ack")

    def read(self, addr: int, sel: int | None = None) -> Any:
        """Perform a classic read; result is stored in ``last_data``."""
        wb = self.wb
        if sel is None:
            sel = self._all_sel()
        rec = TransactionRecord(port=wb.name, address=int(addr), we=False, sel=int(sel))
        rec.start = now()
        wb.adr_o.next = addr
        wb.we_o.next = 0
        wb.sel_o.next = sel
        wb.cyc_o.next = 1
        wb.stb_o.next = 1
        yield self._wait(rec, "read")
        rec.read_data = int(wb.dat_i)
        self.last_data = rec.read_data
        yield self._finish(rec, "ack")

    def rmw(self, addr: int, mask: int, data: int, sel: int | None = None) -> Any:
        """Read-modify-write; result is stored in ``last_data``."""
        yield self.read(addr, sel=sel)
        cur = self.last_data or 0
        new = (cur & ~mask) | (data & mask)
        yield self.write(addr, new, sel=sel)
