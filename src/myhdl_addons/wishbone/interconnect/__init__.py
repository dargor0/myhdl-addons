"""Interconnect strategies.

Exposes the strategy base class and the built-in strategies.  Custom
topologies subclass :class:`InterconnectBase` (``WB-FR-046``).
"""

from .base import InterconnectBase, InterconnectContext
from .crossbar import Crossbar
from .p2p import PointToPoint
from .shared_bus import SharedBus

__all__ = [
    "Crossbar",
    "InterconnectBase",
    "InterconnectContext",
    "PointToPoint",
    "SharedBus",
]
