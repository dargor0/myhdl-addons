"""Register-file / CSR peripheral for Wishbone.

Implements ``WB-FR-070`` (CSR peripheral wrapper), ``WB-FR-072``
(read/write strobes), ``WB-FR-073`` (convertible) and ``WB-FR-074``
(the declarative ``CSRMap`` front-end).

It is a thin Wishbone adapter over the shared, bus-agnostic
:class:`~myhdl_addons.bus_common.regfile.RegisterEngine`: the engine holds the
registers and does the address decode / read mux / strobes, while this wrapper
maps the Wishbone slave handshake (``cyc``/``stb``/``we``/``adr``/``dat``/
``sel``) onto the engine's request interface.

Registers are whole-word and ``width`` bits wide.  Semantics:

* ``add_write(offset, name, init)`` — stored, writable.
* ``add_read(offset, name)``       — readable; the peripheral drives the
  value (via ``csr.signals[name]``).
* ``add_ro(offset, name, init)``   — stored, read-only.

After :meth:`CSRMap.build` the signals and strobes are available as
``csr.signals[name]``, ``csr.wr[name]`` and ``csr.rd[name]``.
"""

from myhdl import Signal, always_comb, block, intbv

from ..bus_common.regfile import CSRMap as _EngineMap
from .checks import WishboneConfigError
from .interface import SlaveView

__all__ = ["READ", "RO", "WRITE", "CSRMap"]

READ = "read"
WRITE = "write"
RO = "ro"


class CSRMap:
    """A declarative, aligned register map for a Wishbone slave."""

    def __init__(self, width: int = 32, name: str = "csr") -> None:
        if width <= 0:
            raise WishboneConfigError("width must be positive")
        self.width = width
        self.name = name
        self._engine = _EngineMap(width=width, gran=8, name=name)

    # -- declarative API ---------------------------------------------------
    def _add(self, offset: int, name: str, kind: str, init: int = 0) -> str:
        regs = self._engine.regs
        if any(r.name == name for r in regs):
            raise WishboneConfigError(f"duplicate register name {name!r}")
        word = self.width // 8
        if offset % word != 0:
            raise WishboneConfigError(f"offset {offset:#x} must be {word}-byte aligned")
        if any(r.offset == offset for r in regs):
            raise WishboneConfigError(f"duplicate offset {offset:#x}")
        if kind == WRITE:
            self._engine.add_write(offset, name, init)
        elif kind == RO:
            self._engine.add_ro(offset, name, init)
        else:
            self._engine.add_read(offset, name)
        return name

    def add_write(self, offset: int, name: str, init: int = 0) -> str:
        """Add a writable, stored register."""
        return self._add(offset, name, WRITE, init)

    def add_read(self, offset: int, name: str) -> str:
        """Add a readable register whose value the peripheral supplies."""
        return self._add(offset, name, READ, 0)

    def add_ro(self, offset: int, name: str, init: int = 0) -> str:
        """Add a read-only, stored register."""
        return self._add(offset, name, RO, init)

    @property
    def signals(self):
        return self._engine.signals

    @property
    def wr(self):
        return self._engine.wr

    @property
    def rd(self):
        return self._engine.rd

    # -- elaboration -------------------------------------------------------
    @block
    def build(self, wb: SlaveView):
        """Create the peripheral and return its MyHDL instances.

        Args:
            wb: a :class:`~myhdl_addons.wishbone.interface.SlaveView`.
        """
        if len(self._engine.regs) == 0:
            raise WishboneConfigError(f"CSRMap {self.name!r} has no registers")

        base = getattr(wb, "base", 0) or 0
        req = Signal(bool(0))
        addr = Signal(intbv(0)[len(wb.adr_i) :])
        err_o = wb.err_o
        # per-lane write strobes only when the bus granularity matches the
        # engine's (byte) granularity; otherwise use whole-word writes.
        wstrb = wb.sel_i if len(wb.sel_i) == self.width // 8 else None

        if err_o is not None:

            @always_comb
            def map_request():
                req.next = wb.cyc_i and wb.stb_i
                # rebase onto the slave window; guard against negative offsets
                if int(wb.adr_i) >= base:
                    addr.next = wb.adr_i - base
                else:
                    addr.next = 0
                # tie ERR low; driven alongside the request so the process has a
                # non-empty sensitivity list (a constant-only @always_comb fails)
                err_o.next = 0

        else:

            @always_comb
            def map_request():
                req.next = wb.cyc_i and wb.stb_i
                # rebase onto the slave window; guard against negative offsets
                if int(wb.adr_i) >= base:
                    addr.next = wb.adr_i - base
                else:
                    addr.next = 0

        proclist = [map_request]
        proclist.append(
            self._engine.build(
                wb.clk,
                wb.rst,
                req,
                wb.we_i,
                addr,
                wb.dat_i,
                wb.dat_o,
                wb.ack_o,
                wstrb=wstrb,
                reset_active=1,
            )
        )

        return proclist
