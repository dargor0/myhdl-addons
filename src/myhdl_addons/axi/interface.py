"""AXI container, ports and directional views.

Implements ``AX-FR-001..008``: a parameterized ``Axi`` container built from an
external ``aclk`` and active-low ``aresetn``, holding one signal set per
master/slave port, exposed through directional views.  Three variants are
supported: ``full`` (AXI4), ``lite`` (AXI4-Lite) and ``stream`` (AXI4-Stream).
Optional user sidebands are enabled with ``user=True`` (``AX-FR-011``).
"""

from __future__ import annotations

from myhdl import Signal, SignalType, block, intbv

from ..bus_common import AddressMap, Trace
from .checks import AxiConfigError, check_variant, check_widths

__all__ = ["Axi", "AxiMasterView", "AxiPort", "AxiSlavePort", "AxiSlaveView"]

# -- signal tables ---------------------------------------------------------
_LITE = (
    "awaddr",
    "awprot",
    "awvalid",
    "awready",
    "wdata",
    "wstrb",
    "wvalid",
    "wready",
    "bresp",
    "bvalid",
    "bready",
    "araddr",
    "arprot",
    "arvalid",
    "arready",
    "rdata",
    "rresp",
    "rvalid",
    "rready",
)
_FULL = (
    "awid",
    "awaddr",
    "awlen",
    "awsize",
    "awburst",
    "awlock",
    "awcache",
    "awprot",
    "awvalid",
    "awready",
    "wdata",
    "wstrb",
    "wlast",
    "wvalid",
    "wready",
    "bid",
    "bresp",
    "bvalid",
    "bready",
    "arid",
    "araddr",
    "arlen",
    "arsize",
    "arburst",
    "arlock",
    "arcache",
    "arprot",
    "arvalid",
    "arready",
    "rid",
    "rdata",
    "rresp",
    "rlast",
    "rvalid",
    "rready",
)
_STREAM = ("tdata", "tlast", "tvalid", "tready")
_STREAM_OPTIONAL = ("tstrb", "tkeep", "tid", "tdest", "tuser")
_FULL_USER_IN = ("awuser", "aruser", "wuser")
_FULL_USER_OUT = ("buser", "ruser")
_FULL_QOS = ("awqos", "arqos", "awregion", "arregion")

#: Optional sidebands driven by the master / by the slave.
FULL_MASTER_OPTIONAL = _FULL_USER_IN + _FULL_QOS
FULL_SLAVE_OPTIONAL = _FULL_USER_OUT
#: Optional AXI4-Stream sidebands.
STREAM_MASTER_OPTIONAL = _STREAM_OPTIONAL

_BOOL = {
    "awvalid",
    "awready",
    "wlast",
    "wvalid",
    "wready",
    "bvalid",
    "bready",
    "arvalid",
    "arready",
    "rlast",
    "rvalid",
    "rready",
    "tlast",
    "tvalid",
    "tready",
    "awlock",
    "arlock",
}
_WIDTH = {
    "awid": "id",
    "arid": "id",
    "bid": "id",
    "rid": "id",
    "tid": "id",
    "tdest": "id",
    "awaddr": "addr",
    "araddr": "addr",
    "awlen": 8,
    "arlen": 8,
    "awsize": 3,
    "arsize": 3,
    "awburst": 2,
    "arburst": 2,
    "awcache": 4,
    "arcache": 4,
    "awprot": 3,
    "arprot": 3,
    "awqos": 4,
    "arqos": 4,
    "awregion": 4,
    "arregion": 4,
    "wdata": "data",
    "rdata": "data",
    "tdata": "data",
    "wstrb": "strb",
    "tstrb": "strb",
    "tkeep": "strb",
    "bresp": 2,
    "rresp": 2,
    "awuser": "user",
    "aruser": "user",
    "wuser": "user",
    "ruser": "user",
    "buser": "user",
    "tuser": "user",
}

#: Direction maps consumed by interconnect strategies.
MASTER_OUT = {
    "lite": (
        "awaddr",
        "awprot",
        "awvalid",
        "wdata",
        "wstrb",
        "wvalid",
        "bready",
        "araddr",
        "arprot",
        "arvalid",
        "rready",
    ),
    "full": (
        "awid",
        "awaddr",
        "awlen",
        "awsize",
        "awburst",
        "awlock",
        "awcache",
        "awprot",
        "awvalid",
        "wdata",
        "wstrb",
        "wlast",
        "wvalid",
        "bready",
        "arid",
        "araddr",
        "arlen",
        "arsize",
        "arburst",
        "arlock",
        "arcache",
        "arprot",
        "arvalid",
        "rready",
    ),
    "stream": ("tdata", "tlast", "tvalid"),
}
SLAVE_OUT = {
    "lite": (
        "awready",
        "wready",
        "bresp",
        "bvalid",
        "arready",
        "rdata",
        "rresp",
        "rvalid",
    ),
    "full": (
        "awready",
        "wready",
        "bid",
        "bresp",
        "bvalid",
        "arready",
        "rid",
        "rdata",
        "rresp",
        "rlast",
        "rvalid",
    ),
    "stream": ("tready",),
}


def _variant_signals(variant: str, user: bool) -> list[str]:
    if variant == "lite":
        return list(_LITE)
    if variant == "stream":
        names = list(_STREAM)
        if user:
            names += list(_STREAM_OPTIONAL)
        return names
    names = list(_FULL)
    if user:
        names += list(_FULL_USER_IN) + list(_FULL_USER_OUT) + list(_FULL_QOS)
    return names


def _make_signal(bus: Axi, name: str) -> SignalType:
    if name in _BOOL:
        return Signal(bool(0))
    width = _WIDTH[name]
    if width == "id":
        width = bus.id_width
    elif width == "addr":
        width = bus.addr_width
    elif width == "data":
        width = bus.data_width
    elif width == "strb":
        width = bus.data_width // 8
    elif width == "user":
        width = bus.user_width
    return Signal(intbv(0)[width:])


class AxiPort:
    """The raw signal set for one AXI port (one endpoint)."""

    def __init__(self, bus: Axi, name: str) -> None:
        self.bus = bus
        self.name = name
        self.variant = bus.variant
        self.aclk = bus.aclk
        self.aresetn = bus.aresetn
        self.clk = bus.clk
        self.rst = bus.rst
        self._names = _variant_signals(bus.variant, bus.user)
        for sig_name in self._names:
            setattr(self, sig_name, _make_signal(bus, sig_name))

    def signal(self, name: str) -> SignalType:
        try:
            return getattr(self, name)
        except AttributeError:
            raise AxiConfigError(f"port {self.name!r} has no signal {name!r}")

    def __repr__(self) -> str:
        return f"AxiPort({self.name!r}, variant={self.variant!r})"


class AxiSlavePort(AxiPort):
    """A port plus its address window (used for decoding)."""

    def __init__(
        self, bus: Axi, name: str, base: int = 0, size: int | None = None
    ) -> None:
        super().__init__(bus, name)
        self.base = base
        self.size = size


class _AxiView:
    """Shared base for master/slave views over an :class:`AxiPort`."""

    def __init__(self, bus: Axi, port: AxiPort) -> None:
        self._bus = bus
        self._port = port
        self.name = port.name
        self.variant = port.variant
        self.aclk = bus.aclk
        self.aresetn = bus.aresetn
        self.clk = bus.clk
        self.rst = bus.rst
        for sig_name in port._names:
            setattr(self, sig_name, getattr(port, sig_name))

    def __getitem__(self, name: str) -> SignalType:
        return getattr(self, name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r}, variant={self.variant!r})"


class AxiMasterView(_AxiView):
    """Master-side view over an :class:`AxiPort`."""


class AxiSlaveView(_AxiView):
    """Slave-side view over an :class:`AxiSlavePort`."""

    def __init__(
        self,
        bus: Axi,
        port: AxiSlavePort,
        base: int = 0,
        size: int | None = None,
    ) -> None:
        super().__init__(bus, port)
        self.base = base
        self.size = size


class Axi:
    """A multi-master / multi-slave AXI container.

    Args:
        aclk, aresetn: externally provided clock and active-low reset.
        data_width, addr_width, id_width, user_width: geometry.
        variant: ``"full"`` (AXI4), ``"lite"`` (AXI4-Lite) or ``"stream"``.
        user: enable optional user sidebands (full variant only).
        interconnect: an :class:`AxiInterconnectBase` strategy.
        trace: enable simulation/debug hooks.
    """

    def __init__(
        self,
        aclk: SignalType,
        aresetn: SignalType,
        data_width: int = 32,
        addr_width: int = 32,
        id_width: int = 4,
        user_width: int = 0,
        *,
        variant: str = "full",
        user: bool = False,
        name: str = "axi",
        interconnect: object | None = None,
        trace: bool = False,
    ) -> None:
        check_widths(data_width, addr_width, id_width, user_width, variant)
        self.aclk = aclk
        self.aresetn = aresetn
        self.clk = aclk
        self.rst = aresetn
        self.data_width = data_width
        self.addr_width = addr_width
        self.id_width = id_width
        self.user_width = user_width
        self.variant = check_variant(variant)
        self.user = bool(user) and self.variant in ("full", "stream")
        if self.user and user_width <= 0:
            raise AxiConfigError("user=True requires user_width > 0")
        self.name = name

        self._masters: list[AxiPort] = []
        self._slaves: list[AxiSlavePort] = []
        self._address_map = AddressMap(addr_width)
        self._interconnect = interconnect
        self._trace = Trace(enabled=trace, bus=self)
        self._built = False

    # -- ports -------------------------------------------------------------
    def add_master(self, name: str | None = None) -> AxiMasterView:
        """Create a master port and return its view."""
        if self._built:
            raise AxiConfigError("cannot add a master after build()")
        port = AxiPort(self, name or f"m{len(self._masters)}")
        self._masters.append(port)
        return AxiMasterView(self, port)

    def add_slave(
        self, base: int = 0, size: int | None = None, name: str | None = None
    ) -> AxiSlaveView:
        """Create a slave port with an address window; return its view."""
        if self._built:
            raise AxiConfigError("cannot add a slave after build()")
        port_name = name or f"s{len(self._slaves)}"
        if size is None and self.variant == "stream":
            size = 1
        check_address_range(base, size, self.addr_width, port_name)
        port = AxiSlavePort(self, port_name, base=base, size=size)
        self._slaves.append(port)
        self._address_map.add(base, size, port_name)
        return AxiSlaveView(self, port, base=base, size=size)

    # -- introspection -----------------------------------------------------
    @property
    def trace(self) -> Trace:
        return self._trace

    @property
    def address_map(self) -> AddressMap:
        return self._address_map

    @property
    def masters(self) -> list[AxiPort]:
        return list(self._masters)

    @property
    def slaves(self) -> list[AxiSlavePort]:
        return list(self._slaves)

    def metadata(self) -> dict[str, object]:
        return {
            "variant": self.variant,
            "reset_name": "aresetn",
            "reset_active": 0,
            "handshake": "valid/ready",
            "data_width": self.data_width,
            "addr_width": self.addr_width,
            "id_width": self.id_width,
            "user_width": self.user_width,
        }

    # -- elaboration -------------------------------------------------------
    @block
    def build(self, interconnect: object | None = None):
        """Elaborate the fabric and return instances (plus trace monitors)."""
        from .interconnect.base import AxiContext, AxiInterconnectBase

        if not self._masters:
            raise AxiConfigError(f"bus {self.name!r} has no master ports")
        if not self._slaves:
            raise AxiConfigError(f"bus {self.name!r} has no slave ports")

        ic = interconnect or self._interconnect
        if ic is None:
            raise AxiConfigError(f"bus {self.name!r} has no interconnect strategy")
        if not isinstance(ic, AxiInterconnectBase):
            raise AxiConfigError(
                f"interconnect must be an AxiInterconnectBase, "
                f"got {type(ic).__name__!r}"
            )

        ctx = AxiContext(self)
        ic.validate(ctx)
        result = ic.build(ctx)
        monitors = self._trace.monitors()
        self._built = True
        return result, monitors


def check_address_range(base: int, size: int | None, adr_width: int, name: str) -> None:
    """Local wrapper so malformed windows raise :class:`AxiConfigError`."""
    from ..bus_common import BusConfigError
    from ..bus_common import check_address_range as _car

    try:
        _car(base, size, adr_width, name)
    except BusConfigError as exc:
        raise AxiConfigError(str(exc)) from exc


# ``SignalType`` is re-exported for callers constructing signals consistently.
__all__ += ["SignalType"]
