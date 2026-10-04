"""Transaction-level AXI reference model for differential checks (``AX-FR-092``).

:class:`AxiMemModel` is a plain-Python (non-simulatable) model of a
memory-mapped AXI slave.  It mirrors the RTL memory slave in
:mod:`myhdl_addons.axi.full`: a single little-endian word-addressed window,
INCR bursts (address advances by ``data_width/8`` per beat) and
``OKAY``/``DECERR`` responses.  Testbenches drive the RTL through a BFM and
compare against the model at the transaction level.
"""

from __future__ import annotations

from typing import Any

from .status import AxiStatus

__all__ = ["AxiMemModel"]


class AxiMemModel:
    """A word-addressed reference model of an AXI memory slave.

    Args:
        data_width: data-bus width in bits.
        addr_width: address-bus width in bits.
        base: base address of the modelled window.
        size: window size in bytes.
        fill: initial value of every word.

    Attributes:
        last_data: beats returned by the most recent :meth:`read`.
        last_resp: :class:`~myhdl_addons.axi.AxiStatus` of the last operation.
    """

    def __init__(
        self,
        data_width: int = 32,
        addr_width: int = 32,
        base: int = 0,
        size: int = 0x100,
        fill: int = 0,
    ) -> None:
        self.data_width = data_width
        self.addr_width = addr_width
        self.nbytes = data_width // 8
        self.shift = self.nbytes.bit_length() - 1
        self.base = base
        self.size = size
        self.words = max(size // self.nbytes, 1)
        self.mask = (1 << data_width) - 1
        self.mem: list[int] = [fill & self.mask for _ in range(self.words)]
        self.last_data: list[int] | None = None
        self.last_resp = AxiStatus.OKAY

    # -- helpers -----------------------------------------------------------
    def in_range(self, addr: int) -> bool:
        """Return whether *addr* falls inside the modelled window."""
        return self.base <= addr < self.base + self.words * self.nbytes

    def _index(self, addr: int) -> int:
        return (addr - self.base) >> self.shift

    def word(self, addr: int) -> int:
        """Return the stored word at *addr* (assumes it is in range)."""
        return self.mem[self._index(addr)]

    def reset(self, fill: int = 0) -> None:
        """Reset every word to *fill* and clear the last response."""
        self.mem = [fill & self.mask for _ in range(self.words)]
        self.last_data = None
        self.last_resp = AxiStatus.OKAY

    # -- transactions ------------------------------------------------------
    def read(self, addr: int, length: int = 1) -> AxiStatus:
        """Model an INCR read; beats land in ``last_data``."""
        data: list[int] = []
        a = addr
        for _ in range(length):
            if not self.in_range(a):
                self.last_data = None
                self.last_resp = AxiStatus.DECERR
                return self.last_resp
            data.append(self.mem[self._index(a)])
            a += self.nbytes
        self.last_data = data
        self.last_resp = AxiStatus.OKAY
        return self.last_resp

    def write(self, addr: int, data: Any, strb: Any = None) -> AxiStatus:
        """Model an INCR write; *data* is an iterable of beats.

        *strb* may be ``None`` (all bytes), an integer strobe applied to every
        beat, or an iterable of per-beat strobes.
        """
        beats = [int(beat) & self.mask for beat in data]
        if strb is None:
            strobes = [self.mask] * len(beats)
        elif isinstance(strb, int):
            strobes = [strb] * len(beats)
        else:
            strobes = list(strb)

        a = addr
        for i, beat in enumerate(beats):
            if not self.in_range(a):
                self.last_resp = AxiStatus.DECERR
                return self.last_resp
            idx = self._index(a)
            word = self.mem[idx]
            merged = word
            for b in range(self.nbytes):
                if (strobes[i] >> b) & 1:
                    lane = 0xFF << (8 * b)
                    merged = (merged & (self.mask ^ lane)) | (beat & lane)
            self.mem[idx] = merged
            a += self.nbytes
        self.last_resp = AxiStatus.OKAY
        return self.last_resp
