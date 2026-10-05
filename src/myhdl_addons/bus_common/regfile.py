"""Generic, bus-agnostic register / CSR engine.

Implements ``CB-FR-070`` (register storage, reset values, read mux and
per-register read/write strobes, independent of any bus), ``CB-FR-071``
(the declarative ``CSRMap`` front-end), ``CB-FR-072`` (register specs and
bitfield utilities), ``CB-FR-073`` (basic escape hatches: externally driven
read registers and W1C) and ``CB-FR-075`` (within the MyHDL convertible
subset).

The engine is driven by a small synchronous request interface:

* inputs: ``req``, ``we``, ``addr``, ``wdata`` and optional ``wstrb``
* outputs: ``rdata`` and ``ack``

A per-bus slave wrapper (``CB-FR-074``) maps its handshake/strobes onto
those signals; the engine itself never mentions a bus.
"""

from typing import Any

from myhdl import Signal, SignalType, always, always_comb, block, intbv

from .errors import BusConfigError
from .params import check_alignment, check_positive_int

__all__ = [
    "READ",
    "RO",
    "WRITE",
    "CSRMap",
    "RegisterEngine",
    "RegisterSpec",
    "bitfield",
    "bitfield_set",
]

READ = "read"
WRITE = "write"
RO = "ro"


def bitfield(value: int | intbv, lsb: int, width: int) -> int:
    """Extract the ``width``-bit field starting at *lsb* from *value*."""
    return (int(value) >> lsb) & ((1 << width) - 1)


def bitfield_set(value: int | intbv, lsb: int, width: int, field: int) -> int:
    """Return *value* with the ``width``-bit field at *lsb* set to *field*."""
    mask = ((1 << width) - 1) << lsb
    return (int(value) & ~mask) | ((int(field) << lsb) & mask)


class RegisterSpec:
    """A declarative register/field description (``CB-FR-072``)."""

    __slots__ = ("access", "name", "offset", "reset", "source", "w1c", "width")

    def __init__(
        self,
        name: str,
        offset: int,
        width: int,
        access: str,
        reset: int = 0,
        w1c: bool = False,
        source: Any = None,
    ) -> None:
        self.name = name
        self.offset = offset
        self.width = width
        self.access = access
        self.reset = reset
        self.w1c = bool(w1c)
        self.source = source

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__}

    def __repr__(self) -> str:
        return (
            f"RegisterSpec({self.name!r}, offset={self.offset:#x}, "
            f"width={self.width}, access={self.access!r})"
        )


@block
def engine_match(addr, offset, match):
    """Combinational address match for one register (``addr == offset``)."""

    @always_comb
    def p():
        match.next = int(addr) == offset

    return p


@block
def engine_cell(clk, rst, reset_active, req, we, addr, offset, d, q, init):
    """Stored register cell: reset (optional) > write > hold.

    The address compare is done *inside* the clocked process so a new ``addr``
    presented together with the clock edge is sampled correctly.
    """

    if reset_active is None:

        @always(clk.posedge)
        def p():
            if req and we and (int(addr) == offset):
                q.next = d

    else:

        @always(clk.posedge)
        def p():
            if rst == reset_active:
                q.next = init
            else:
                if req and we and (int(addr) == offset):
                    q.next = d

    return p


@block
def engine_cell_w1c(
    clk, rst, reset_active, req, we, addr, offset, q, wdata, full, init
):
    """Write-1-to-clear cell: ``q & (wdata ^ full)`` computed at the edge."""

    if reset_active is None:

        @always(clk.posedge)
        def p():
            if req and we and (int(addr) == offset):
                q.next = q & (wdata ^ full)

    else:

        @always(clk.posedge)
        def p():
            if rst == reset_active:
                q.next = init
            else:
                if req and we and (int(addr) == offset):
                    q.next = q & (wdata ^ full)

    return p


@block
def engine_cell_wstrb(
    clk,
    rst,
    reset_active,
    req,
    we,
    addr,
    offset,
    q,
    wdata,
    wstrb,
    mask_rom,
    keep_rom,
    init,
):
    """Byte-strobe cell: merge ``wdata``/``q`` per lane at the edge.

    The strobe-to-mask expansion is a ROM lookup (a tuple of ints), keeping the
    whole merge inside the clocked process.
    """

    if reset_active is None:

        @always(clk.posedge)
        def p():
            if req and we and (int(addr) == offset):
                mask = mask_rom[int(wstrb)]
                keep = keep_rom[int(wstrb)]
                q.next = (q & keep) | (wdata & mask)

    else:

        @always(clk.posedge)
        def p():
            if rst == reset_active:
                q.next = init
            else:
                if req and we and (int(addr) == offset):
                    mask = mask_rom[int(wstrb)]
                    keep = keep_rom[int(wstrb)]
                    q.next = (q & keep) | (wdata & mask)

    return p


@block
def engine_ro(clk, rst, reset_active, q, init):
    """Read-only (stored, constant) register cell."""

    if reset_active is None:

        @always(clk.posedge)
        def p():
            q.next = init

    else:

        @always(clk.posedge)
        def p():
            if rst == reset_active:
                q.next = init

    return p


@block
def engine_strobe(req, we, match, rd, wr, is_write):
    """Per-register read/write strobe logic."""

    if is_write:

        @always_comb
        def p():
            rd.next = req and match and (not we)
            wr.next = req and match and we

    else:

        @always_comb
        def p():
            rd.next = req and match and (not we)
            wr.next = 0

    return p


@block
def engine_ack(req, ack):
    @always_comb
    def p():
        ack.next = req

    return p


@block
def engine_read_stage(match, value, acc, dst, first):
    """One stage of the read-mux chain: select ``value`` when ``match``.

    Registers are non-overlapping, so a priority chain over individual signals
    is equivalent to an indexed mux while avoiding a list-of-signals (which
    MyHDL would convert to an invalid, continuously-assigned Verilog memory).
    """

    if first:

        @always_comb
        def p():
            if match:
                dst.next = value
            else:
                dst.next = 0

    else:

        @always_comb
        def p():
            if match:
                dst.next = value
            else:
                dst.next = acc

    return p


class RegisterEngine:
    """A generic register file with stored, read-only and driven registers."""

    def __init__(self, width: int = 32, gran: int = 8, name: str = "regs") -> None:
        check_positive_int(width, "width")
        check_positive_int(gran, "gran")
        if width % gran != 0:
            raise BusConfigError(f"width ({width}) must be a multiple of gran ({gran})")
        self.width = width
        self.gran = gran
        self.strb_width = width // gran
        self.name = name
        self._regs: list[RegisterSpec] = []
        self._by_name: dict[str, RegisterSpec] = {}
        self.signals: dict[str, SignalType] = {}
        self.wr: dict[str, SignalType] = {}
        self.rd: dict[str, SignalType] = {}

    # -- declarative API ---------------------------------------------------
    def _add(
        self,
        offset: int,
        name: str,
        access: str,
        init: int = 0,
        w1c: bool = False,
        source: Any = None,
    ) -> RegisterSpec:
        if access not in (READ, WRITE, RO):
            raise BusConfigError(f"unknown access {access!r}")
        if not isinstance(name, str) or not name:
            raise BusConfigError("register name must be a non-empty string")
        if name in self._by_name:
            raise BusConfigError(f"duplicate register name {name!r}")
        word = self.width // 8
        check_alignment(offset, word, "offset")
        for reg in self._regs:
            if reg.offset == offset:
                raise BusConfigError(f"duplicate offset {offset:#x}")
        spec = RegisterSpec(name, offset, self.width, access, init, w1c, source)
        self._regs.append(spec)
        self._by_name[name] = spec
        return spec

    def add(
        self,
        offset: int,
        name: str,
        access: str = WRITE,
        init: int = 0,
        w1c: bool = False,
        source: Any = None,
    ) -> RegisterSpec:
        """Add a register described by an explicit access mode."""
        return self._add(offset, name, access, init, w1c, source)

    def add_write(
        self, offset: int, name: str, init: int = 0, w1c: bool = False
    ) -> RegisterSpec:
        """Add a writable, stored register (optionally write-1-to-clear)."""
        return self._add(offset, name, WRITE, init, w1c)

    def add_read(self, offset: int, name: str, source: Any = None) -> RegisterSpec:
        """Add a readable register whose value is driven externally."""
        return self._add(offset, name, READ, 0, False, source)

    def add_ro(self, offset: int, name: str, init: int = 0) -> RegisterSpec:
        """Add a read-only, stored register."""
        return self._add(offset, name, RO, init)

    @property
    def regs(self) -> list[RegisterSpec]:
        return list(self._regs)

    def spec(self, name: str) -> RegisterSpec:
        return self._by_name[name]

    # -- elaboration -------------------------------------------------------
    @block
    def build(
        self,
        clk: SignalType,
        rst: SignalType,
        req: SignalType,
        we: SignalType,
        addr: SignalType,
        wdata: SignalType,
        rdata: SignalType,
        ack: SignalType,
        wstrb: SignalType | None = None,
        reset_active: int | None = 1,
    ):
        """Create the register file and return its MyHDL instances.

        Args:
            clk, rst: clock and reset signals (external).
            req, we: request and write-enable control signals.
            addr: byte address ``Signal(intbv)``.
            wdata, rdata: write/read data ``Signal(intbv)``.
            ack: response/ready ``Signal(bool)``.
            wstrb: optional write-strobe ``Signal(intbv)`` (one bit per lane).
            reset_active: asserted level of *rst* (``None`` ignores reset).
        """
        regs = self._regs
        n = len(regs)
        if n == 0:
            raise BusConfigError(f"register engine {self.name!r} has no registers")

        width = self.width
        full = (1 << width) - 1
        lane = self.gran
        lanes = self.strb_width
        lane_masks = [((1 << lane) - 1) << (b * lane) for b in range(lanes)]
        if wstrb is not None:
            mask_rom = tuple(
                sum(lane_masks[b] for b in range(lanes) if (s >> b) & 1)
                for s in range(1 << lanes)
            )
            keep_rom = tuple(full ^ m for m in mask_rom)
        else:
            mask_rom = keep_rom = None

        signals = [Signal(intbv(r.reset)[width:]) for r in regs]
        wr = [Signal(bool(0)) for _ in range(n)]
        rd = [Signal(bool(0)) for _ in range(n)]

        self.signals = {r.name: s for r, s in zip(regs, signals)}
        self.wr = {r.name: s for r, s in zip(regs, wr)}
        self.rd = {r.name: s for r, s in zip(regs, rd)}

        proclist = []

        matches = [Signal(bool(0)) for _ in range(n)]
        for i, reg in enumerate(regs):
            proclist.append(engine_match(addr, reg.offset, matches[i]))

        for i, reg in enumerate(regs):
            cell = signals[i]
            if reg.access == WRITE:
                if reg.w1c:
                    proclist.append(
                        engine_cell_w1c(
                            clk,
                            rst,
                            reset_active,
                            req,
                            we,
                            addr,
                            reg.offset,
                            cell,
                            wdata,
                            full,
                            reg.reset,
                        )
                    )
                elif wstrb is not None:
                    proclist.append(
                        engine_cell_wstrb(
                            clk,
                            rst,
                            reset_active,
                            req,
                            we,
                            addr,
                            reg.offset,
                            cell,
                            wdata,
                            wstrb,
                            mask_rom,
                            keep_rom,
                            reg.reset,
                        )
                    )
                else:
                    proclist.append(
                        engine_cell(
                            clk,
                            rst,
                            reset_active,
                            req,
                            we,
                            addr,
                            reg.offset,
                            wdata,
                            cell,
                            reg.reset,
                        )
                    )
                proclist.append(engine_strobe(req, we, matches[i], rd[i], wr[i], True))
            elif reg.access == RO:
                proclist.append(engine_ro(clk, rst, reset_active, cell, reg.reset))
                proclist.append(engine_strobe(req, we, matches[i], rd[i], wr[i], False))
            else:  # READ: externally driven value, no storage process
                proclist.append(engine_strobe(req, we, matches[i], rd[i], wr[i], False))

        proclist.append(engine_ack(req, ack))

        acc = 0
        for i in range(n):
            dst = rdata if i == n - 1 else Signal(intbv(0)[width:])
            proclist.append(engine_read_stage(matches[i], signals[i], acc, dst, i == 0))
            acc = dst

        return proclist


class CSRMap(RegisterEngine):
    """Declarative CSR front-end over :class:`RegisterEngine` (``CB-FR-071``)."""

    def __init__(self, width: int = 32, gran: int = 8, name: str = "csr") -> None:
        super().__init__(width=width, gran=gran, name=name)
