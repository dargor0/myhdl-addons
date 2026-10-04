"""AXI interconnect strategy base (``AX-FR-064``)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from myhdl import SignalType

from ...bus_common import AddressMap, Trace

__all__ = ["AxiContext", "AxiInterconnectBase"]


class AxiContext:
    """Everything an AXI fabric strategy needs at elaboration time."""

    def __init__(self, bus: Any) -> None:
        self.bus = bus
        self.aclk: SignalType = bus.aclk
        self.aresetn: SignalType = bus.aresetn
        self.clk = bus.clk
        self.rst = bus.rst
        self.masters = list(bus._masters)
        self.slaves = list(bus._slaves)
        self.address_map: AddressMap = bus._address_map
        self.variant = bus.variant
        self.data_width = bus.data_width
        self.addr_width = bus.addr_width
        self.id_width = bus.id_width
        self.user_width = bus.user_width
        self.user = bus.user
        self.trace = getattr(bus, "trace", Trace())


class AxiInterconnectBase(ABC):
    """Base class for pluggable AXI fabric strategies."""

    name = "interconnect"

    @abstractmethod
    def build(self, ctx: AxiContext) -> Any:
        """Return an iterable of MyHDL instances implementing the fabric."""

    def validate(self, ctx: AxiContext) -> None:
        """Validate the topology for *ctx*; raise on an illegal configuration."""
