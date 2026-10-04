"""Interconnect strategy base classes.

Implements ``WB-FR-045`` (abstract ``InterconnectBase`` driven by the
container), ``WB-FR-046`` (user subclasses define new topologies) and
``WB-FR-049a`` (the container supplies ports + address map; the strategy
builds the routing logic).
"""

# PEP 563: ``Wishbone`` is imported only under ``TYPE_CHECKING`` below, so the
# annotations on ``InterconnectContext`` must not be evaluated at runtime.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from myhdl import SignalType

if TYPE_CHECKING:
    from ..interface import MasterPort, SlavePort, Wishbone

__all__ = ["InterconnectBase", "InterconnectContext"]


class InterconnectContext:
    """Everything an interconnect strategy needs at elaboration time.

    Attributes:
        bus: the owning :class:`~myhdl_addons.wishbone.interface.Wishbone`.
        clk, rst: shared clock/reset.
        masters: list of :class:`MasterPort`.
        slaves: list of :class:`SlavePort` (each has ``base``/``size``).
        data_width, adr_width, gran, sel_width: bus geometry.
        err, rty, lock: optional-signal enable flags.
    """

    def __init__(self, bus: Wishbone) -> None:
        self.bus = bus
        self.clk: SignalType = bus.clk
        self.rst: SignalType = bus.rst
        self.masters: list[MasterPort] = list(bus._masters)
        self.slaves: list[SlavePort] = list(bus._slaves)
        self.data_width = bus.data_width
        self.adr_width = bus.adr_width
        self.gran = bus.gran
        self.sel_width = bus.sel_width
        self.err = bus.err
        self.rty = bus.rty
        self.lock = bus.lock


class InterconnectBase:
    """Base class for pluggable interconnect strategies.

    Subclasses implement :meth:`build` and return MyHDL instances.  The
    ``build`` method may be called once per container (``WB-FR-048``).
    """

    name = "interconnect"

    def build(self, ctx: InterconnectContext) -> Any:
        """Return an iterable of MyHDL instances implementing the fabric.

        Args:
            ctx (InterconnectContext): ports, address map and parameters.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement build()")
