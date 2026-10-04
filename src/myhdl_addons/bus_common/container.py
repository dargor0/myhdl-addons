"""Bus container base class.

Implements ``CB-FR-030`` (container built from an external clock/reset with
``add_master`` / ``add_slave`` / ``build`` / ``trace``), ``CB-FR-031``
(shared container behaviour provided once), ``CB-FR-032`` (protocol metadata
and port/address-map exposure) and ``CB-FR-033`` (routing delegated to the
selected strategy).
"""

from typing import Any

from myhdl import SignalType, block

from .addrmap import AddressMap
from .checks import check_address_range, check_signal_type
from .errors import BusConfigError
from .interconnect import InterconnectBase, InterconnectContext
from .params import check_multiple_of, check_positive_int
from .port import PortBase, ViewBase
from .trace import Trace

__all__ = ["BusContainerBase"]


class BusContainerBase:
    """Protocol-agnostic container for a multi-master / multi-slave bus.

    Per-bus subclasses set the class attributes (:attr:`port_cls`,
    :attr:`master_view_cls`, :attr:`slave_view_cls`, :attr:`reset_name`,
    :attr:`reset_active`, :attr:`handshake`) and may override
    :meth:`make_context`.
    """

    reset_name: str = "rst"
    reset_active: int = 1
    handshake: str = "generic"
    port_cls: type[PortBase] | None = None
    master_view_cls: type[ViewBase] | None = None
    slave_view_cls: type[ViewBase] | None = None

    def __init__(
        self,
        clk: SignalType,
        rst: SignalType,
        data_width: int = 32,
        adr_width: int = 16,
        gran: int = 8,
        *,
        name: str = "bus",
        interconnect: InterconnectBase | None = None,
        trace: bool = False,
    ) -> None:
        check_positive_int(data_width, "data_width")
        check_positive_int(adr_width, "adr_width")
        check_positive_int(gran, "gran")
        check_multiple_of(data_width, gran, "data_width")
        check_signal_type(clk, "clk", kind="bool")
        check_signal_type(rst, "rst", kind="bool")

        self.clk = clk
        self.rst = rst
        self.data_width = data_width
        self.adr_width = adr_width
        self.gran = gran
        self.sel_width = data_width // gran
        self.name = name

        self._masters: list[PortBase] = []
        self._slaves: list[PortBase] = []
        self._address_map = AddressMap(adr_width)
        self._interconnect = interconnect
        self._trace = Trace(enabled=trace, bus=self)
        self._built = False

    # -- subclass hooks ----------------------------------------------------
    def make_port(self, name: str, base: int = 0, size: int | None = None) -> PortBase:
        """Create a port; subclasses override with their protocol signals."""
        if self.port_cls is None:
            return PortBase(name, clk=self.clk, rst=self.rst)
        return self.port_cls(self, name, base=base, size=size)

    def make_master_view(self, port: PortBase) -> ViewBase:
        if self.master_view_cls is None:
            return ViewBase(port, self.clk, self.rst)
        return self.master_view_cls(self, port)

    def make_slave_view(self, port: PortBase) -> ViewBase:
        if self.slave_view_cls is None:
            return ViewBase(port, self.clk, self.rst)
        return self.slave_view_cls(self, port)

    def make_context(self) -> InterconnectContext:
        """Build the :class:`InterconnectContext` handed to the strategy."""
        return InterconnectContext(
            self,
            self._masters,
            self._slaves,
            self._address_map,
            self.clk,
            self.rst,
            self.data_width,
            self.adr_width,
            self.gran,
        )

    # -- introspection -----------------------------------------------------
    @property
    def trace(self) -> Trace:
        return self._trace

    @property
    def address_map(self) -> AddressMap:
        return self._address_map

    @property
    def masters(self) -> list[PortBase]:
        return list(self._masters)

    @property
    def slaves(self) -> list[PortBase]:
        return list(self._slaves)

    def metadata(self) -> dict[str, Any]:
        """Return the protocol metadata recorded by the subclass."""
        return {
            "reset_name": self.reset_name,
            "reset_active": self.reset_active,
            "handshake": self.handshake,
            "data_width": self.data_width,
            "adr_width": self.adr_width,
            "gran": self.gran,
        }

    # -- ports -------------------------------------------------------------
    def add_master(self, name: str | None = None) -> ViewBase:
        """Create a master port and return its directional view."""
        if self._built:
            raise BusConfigError("cannot add a master after build()")
        port = self.make_port(name or f"m{len(self._masters)}")
        self._masters.append(port)
        return self.make_master_view(port)

    def add_slave(
        self, base: int = 0, size: int | None = None, name: str | None = None
    ) -> ViewBase:
        """Create a slave port with an address window; return its view."""
        if self._built:
            raise BusConfigError("cannot add a slave after build()")
        port_name = name or f"s{len(self._slaves)}"
        check_address_range(base, size, self.adr_width, port_name)
        port = self.make_port(port_name, base=base, size=size)
        port.base = base
        port.size = size
        self._slaves.append(port)
        self._address_map.add(base, size, port_name)
        return self.make_slave_view(port)

    # -- elaboration -------------------------------------------------------
    @block
    def build(self, interconnect: InterconnectBase | None = None):
        """Elaborate the interconnect and return its MyHDL instances."""
        if not self._masters:
            raise BusConfigError(f"bus {self.name!r} has no master ports")
        if not self._slaves:
            raise BusConfigError(f"bus {self.name!r} has no slave ports")

        ic = interconnect or self._interconnect
        if ic is None:
            raise BusConfigError(f"bus {self.name!r} has no interconnect strategy")
        if not isinstance(ic, InterconnectBase):
            raise BusConfigError(
                f"interconnect must be an InterconnectBase, got {type(ic).__name__!r}"
            )

        ctx = self.make_context()
        ic.validate(ctx)
        result = ic.build(ctx)
        monitors = self._trace.monitors()
        self._built = True
        return result, monitors
