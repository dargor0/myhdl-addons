"""Interconnect strategy base classes and fabric helpers.

Implements ``CB-FR-040`` (abstract ``InterconnectBase`` and
``InterconnectContext``), ``CB-FR-041`` (bus-independent fabric helpers that
compose the common arbiter and decoder) and ``CB-FR-043`` (selection at
construction, topology validation at elaboration).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from myhdl import SignalType, block

from .addrmap import AddressMap, address_decoder
from .arbiter import ArbiterBase
from .errors import BusConfigError
from .port import PortBase

__all__ = [
    "InterconnectBase",
    "InterconnectContext",
    "arbiter_block",
    "decoder_block",
]


class InterconnectContext:
    """Everything an interconnect strategy needs at elaboration time.

    The common layer only ever touches the protocol-agnostic parts
    (ports, address map, geometry, clock/reset, optional-signal flags); the
    per-bus subclass may add protocol-specific attributes.
    """

    def __init__(
        self,
        bus: Any = None,
        masters: Sequence[PortBase] = (),
        slaves: Sequence[PortBase] = (),
        address_map: AddressMap | None = None,
        clk: SignalType | None = None,
        rst: SignalType | None = None,
        data_width: int | None = None,
        adr_width: int | None = None,
        gran: int | None = None,
        flags: dict[str, Any] | None = None,
    ) -> None:
        self.bus = bus
        self.masters = list(masters)
        self.slaves = list(slaves)
        self.address_map = address_map
        self.clk = clk if clk is not None else getattr(bus, "clk", None)
        self.rst = rst if rst is not None else getattr(bus, "rst", None)
        self.data_width = (
            data_width if data_width is not None else getattr(bus, "data_width", None)
        )
        self.adr_width = (
            adr_width if adr_width is not None else getattr(bus, "adr_width", None)
        )
        self.gran = gran if gran is not None else getattr(bus, "gran", None)
        self.flags = dict(flags) if flags else {}

    def geometry(self) -> dict[str, Any]:
        return {
            "data_width": self.data_width,
            "adr_width": self.adr_width,
            "gran": self.gran,
        }


class InterconnectBase(ABC):
    """Base class for pluggable interconnect strategies.

    Subclasses implement :meth:`build`; :meth:`validate` may reject an
    illegal topology at elaboration time (``CB-FR-043``).
    """

    name = "interconnect"

    @abstractmethod
    def build(self, ctx: InterconnectContext) -> Any:
        """Return an iterable of MyHDL instances implementing the fabric."""

    def validate(self, ctx: InterconnectContext) -> None:
        """Validate the topology for *ctx*; raise on an illegal configuration."""


@block
def arbiter_block(
    arbiter: ArbiterBase,
    clk: SignalType | None,
    rst: SignalType | None,
    requests: Sequence[SignalType],
    grants: Sequence[SignalType],
):
    """Instantiate a common ``ArbiterBase`` strategy (``CB-FR-041``)."""
    return arbiter.block(clk, rst, requests, grants)


@block
def decoder_block(
    address_map: AddressMap,
    adr: SignalType,
    selects: Sequence[SignalType],
):
    """Instantiate the common address decoder from an ``AddressMap``."""
    if len(selects) != len(address_map.regions):
        raise BusConfigError(
            f"expected {len(address_map.regions)} selects for the "
            f"address map, got {len(selects)}"
        )
    return address_decoder(adr, selects, address_map.bases(), address_map.sizes())
