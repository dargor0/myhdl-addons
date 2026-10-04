"""Wishbone bus container, ports and directional views.

Implements ``WB-FR-001`` (container with external ``clk``/``rst``),
``WB-FR-003`` (master/slave ``_o``/``_i`` naming), ``WB-FR-004`` (optional
signals), ``WB-FR-005`` (derived ``SEL`` width), ``WB-FR-006``/``WB-FR-010``
(clock/reset injection + optional extra domains), ``WB-FR-007`` (single
interface object), ``WB-FR-008``/``WB-FR-009`` (multi-master/multi-slave
ports and views) and ``WB-FR-002`` (MyHDL signal types).
"""

# PEP 563: ``Wishbone`` is referenced in the port/view constructor and method
# annotations below but is defined at the bottom of this module.  Deferring
# annotation evaluation keeps importing the module from raising NameError.
from __future__ import annotations

from myhdl import Signal, SignalType, block, intbv

from .checks import check_address_range, check_signal_type, check_widths
from .interconnect import InterconnectBase, InterconnectContext, SharedBus
from .trace import Trace

__all__ = ["MasterPort", "MasterView", "SlavePort", "SlaveView", "Wishbone"]


class MasterPort:
    """The raw signal set for one bus port.

    The same signal objects are exposed with directional names through
    :class:`MasterView` (master side) or :class:`SlaveView` (slave side).
    """

    def __init__(self, bus: Wishbone, name: str) -> None:
        self.bus = bus
        self.name = name
        dw, aw, sw = bus.data_width, bus.adr_width, bus.sel_width

        self.cyc = Signal(bool(0))
        self.stb = Signal(bool(0))
        self.we = Signal(bool(0))
        self.adr = Signal(intbv(0)[aw:])
        self.dat_w = Signal(intbv(0)[dw:])
        self.sel = Signal(intbv(0)[sw:])

        self.ack = Signal(bool(0))
        self.dat_r = Signal(intbv(0)[dw:])

        self.err = Signal(bool(0)) if bus.err else None
        self.rty = Signal(bool(0)) if bus.rty else None
        self.lock = Signal(bool(0)) if bus.lock else None


class SlavePort(MasterPort):
    """A port plus its address window (used for decoding)."""

    def __init__(
        self, bus: Wishbone, name: str, base: int = 0, size: int | None = None
    ) -> None:
        super().__init__(bus, name)
        self.base = base
        self.size = size


class MasterView:
    """Master-side directional view over a :class:`MasterPort`."""

    def __init__(self, bus: Wishbone, port: MasterPort) -> None:
        self._bus = bus
        self._port = port
        self.name = port.name
        self.clk = bus.clk
        self.rst = bus.rst
        # driven by the master
        self.cyc_o = port.cyc
        self.stb_o = port.stb
        self.we_o = port.we
        self.adr_o = port.adr
        self.dat_o = port.dat_w
        self.sel_o = port.sel
        self.lock_o = port.lock
        # sampled by the master
        self.ack_i = port.ack
        self.dat_i = port.dat_r
        self.err_i = port.err
        self.rty_i = port.rty

    def __repr__(self) -> str:
        return f"MasterView({self.name})"


class SlaveView:
    """Slave-side directional view over a :class:`SlavePort`."""

    def __init__(
        self,
        bus: Wishbone,
        port: SlavePort,
        base: int = 0,
        size: int | None = None,
    ) -> None:
        self._bus = bus
        self._port = port
        self.name = port.name
        self.clk = bus.clk
        self.rst = bus.rst
        self.base = base
        self.size = size
        # sampled by the slave
        self.cyc_i = port.cyc
        self.stb_i = port.stb
        self.we_i = port.we
        self.adr_i = port.adr
        self.dat_i = port.dat_w
        self.sel_i = port.sel
        self.lock_i = port.lock
        # driven by the slave
        self.ack_o = port.ack
        self.dat_o = port.dat_r
        self.err_o = port.err
        self.rty_o = port.rty

    def __repr__(self) -> str:
        return f"SlaveView({self.name}, base={self.base:#x}, size={self.size})"


class Wishbone:
    """A multi-master / multi-slave Wishbone bus container.

    Args:
        clk, rst: externally provided clock and reset signals (mandatory).
        data_width, adr_width, gran: bus geometry.
        err, rty, lock: enable optional Wishbone signals.
        interconnect: an
            :class:`~myhdl_addons.wishbone.interconnect.base.InterconnectBase`
            instance; when omitted a shared bus is used.
        trace: enable simulation/debug hooks (see :mod:`...trace`).
    """

    def __init__(
        self,
        clk: SignalType,
        rst: SignalType,
        data_width: int = 32,
        adr_width: int = 16,
        gran: int = 8,
        *,
        err: bool = False,
        rty: bool = False,
        lock: bool = False,
        name: str = "wb",
        interconnect: InterconnectBase | None = None,
        trace: bool = False,
    ) -> None:
        check_widths(data_width, adr_width, gran)
        check_signal_type(clk, "clk", kind="bool")
        check_signal_type(rst, "rst", kind="bool")

        self.clk = clk
        self.rst = rst
        self.data_width = data_width
        self.adr_width = adr_width
        self.gran = gran
        self.sel_width = data_width // gran
        self.err = bool(err)
        self.rty = bool(rty)
        self.lock = bool(lock)
        self.name = name

        self._masters: list[MasterPort] = []
        self._slaves: list[SlavePort] = []
        self._interconnect = interconnect
        self._trace = Trace(enabled=trace, bus=self)
        self._built = False

    # -- ports -------------------------------------------------------------
    def add_master(self, name: str | None = None) -> MasterView:
        """Create a master port and return its :class:`MasterView`."""
        if self._built:
            raise RuntimeError("cannot add a master after build()")
        port = MasterPort(self, name or f"m{len(self._masters)}")
        self._masters.append(port)
        return MasterView(self, port)

    def add_slave(
        self, base: int = 0, size: int | None = None, name: str | None = None
    ) -> SlaveView:
        """Create a slave port with an address window; return its view."""
        if self._built:
            raise RuntimeError("cannot add a slave after build()")
        check_address_range(base, size, self.adr_width, name or f"s{len(self._slaves)}")
        port = SlavePort(self, name or f"s{len(self._slaves)}", base=base, size=size)
        self._slaves.append(port)
        return SlaveView(self, port, base=base, size=size)

    # -- tracing -----------------------------------------------------------
    @property
    def trace(self) -> Trace:
        return self._trace

    # -- elaboration -------------------------------------------------------
    @block
    def build(self, interconnect: InterconnectBase | None = None):
        """Elaborate the interconnect and return its MyHDL instances.

        The result is a block suitable to be returned from a top-level
        ``@block`` (together with the attached blocks).  Trace monitors are
        appended automatically.
        """
        if not self._masters:
            raise RuntimeError(f"bus {self.name!r} has no master ports")
        if not self._slaves:
            raise RuntimeError(f"bus {self.name!r} has no slave ports")

        ic = interconnect or self._interconnect or SharedBus()
        if not isinstance(ic, InterconnectBase):
            raise TypeError(
                f"interconnect must be an InterconnectBase, got {type(ic).__name__!r}"
            )

        ctx = InterconnectContext(self)
        result = ic.build(ctx)
        monitors = self._trace.monitors()
        self._built = True
        return result, monitors
