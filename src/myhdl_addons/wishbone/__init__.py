"""Wishbone B4 library for MyHDL.

Public API::

    from myhdl_addons.wishbone import (
        Wishbone, PointToPoint, SharedBus, Crossbar,
        CSRMap, WishboneBFM,
    )

See the repository ``reqs/01_wishbone_lib.md`` for the requirement set this
package implements.
"""

from .arbiter import ArbiterBase, FixedPriorityArbiter
from .bfm import WishboneBFM
from .checks import (
    WishboneConfigError,
    WishboneError,
    WishboneTypeError,
)
from .decoder import AddressMap, address_decoder
from .interconnect import (
    Crossbar,
    InterconnectBase,
    InterconnectContext,
    PointToPoint,
    SharedBus,
)
from .interface import MasterPort, MasterView, SlavePort, SlaveView, Wishbone
from .master import wishbone_master
from .regfile import CSRMap
from .slave import wishbone_slave
from .trace import Trace

__all__ = [
    "AddressMap",
    "ArbiterBase",
    "CSRMap",
    "Crossbar",
    "FixedPriorityArbiter",
    "InterconnectBase",
    "InterconnectContext",
    "MasterPort",
    "MasterView",
    "PointToPoint",
    "SharedBus",
    "SlavePort",
    "SlaveView",
    "Trace",
    "Wishbone",
    "WishboneBFM",
    "WishboneConfigError",
    "WishboneError",
    "WishboneTypeError",
    "address_decoder",
    "wishbone_master",
    "wishbone_slave",
]
