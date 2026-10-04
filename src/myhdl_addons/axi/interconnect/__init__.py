"""AXI interconnect strategies."""

from .base import AxiContext, AxiInterconnectBase
from .crossbar import AxiCrossbar
from .p2p import AxiPointToPoint
from .shared_bus import AxiSharedBus

__all__ = [
    "AxiContext",
    "AxiCrossbar",
    "AxiInterconnectBase",
    "AxiPointToPoint",
    "AxiSharedBus",
]
