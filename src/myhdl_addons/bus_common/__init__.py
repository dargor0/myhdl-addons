"""Common bus layer for myhdl-addons (``myhdl_addons.bus_common``).

Protocol-agnostic base classes, services and rules shared by the Wishbone,
AXI, OBI and TileLink libraries (see ``reqs/00_common_bus_lib.md``).

Nothing here is protocol-specific: the per-bus sub-packages subclass these
types and add their own signals, handshakes and operations.
"""

from ..common.views import SignalView, connect
from .adapter import AdapterBase
from .addrmap import AddressMap, address_decoder
from .arbiter import ArbiterBase, FixedPriorityArbiter, RoundRobinArbiter
from .bfm import BFMBase, StreamBFMBase
from .bits import all_enables, byte_count, enable_width
from .checks import (
    DEFAULT_CHECKS,
    Check,
    CheckRegistry,
    Severity,
    check_address_range,
    check_signal_direction,
    check_signal_type,
    check_signal_width,
)
from .container import BusContainerBase
from .errors import (
    BusConfigError,
    BusError,
    BusProtocolError,
    BusTypeError,
)
from .interconnect import InterconnectBase, InterconnectContext
from .params import (
    check_alignment,
    check_multiple_of,
    check_positive_int,
    check_power_of_two,
    check_range,
    get_preset,
    list_presets,
    register_preset,
)
from .port import PortBase, ViewBase
from .records import (
    BusStatus,
    ContentionEvent,
    Direction,
    ErrorEvent,
    TransactionRecord,
    extend_bus_status,
)
from .regfile import (
    READ,
    RO,
    WRITE,
    CSRMap,
    RegisterEngine,
    RegisterSpec,
    bitfield,
    bitfield_set,
)
from .trace import Trace

__all__ = [
    "DEFAULT_CHECKS",
    "READ",
    "RO",
    "WRITE",
    "AdapterBase",
    # address map
    "AddressMap",
    # arbiter
    "ArbiterBase",
    # testbenches
    "BFMBase",
    "BusConfigError",
    "BusContainerBase",
    # errors
    "BusError",
    "BusProtocolError",
    # records
    "BusStatus",
    "BusTypeError",
    "CSRMap",
    "Check",
    "CheckRegistry",
    "ContentionEvent",
    "Direction",
    "ErrorEvent",
    "FixedPriorityArbiter",
    "InterconnectBase",
    "InterconnectContext",
    # port / container / interconnect
    "PortBase",
    # register engine
    "RegisterEngine",
    "RegisterSpec",
    "RoundRobinArbiter",
    # checks
    "Severity",
    "SignalView",
    "StreamBFMBase",
    # trace
    "Trace",
    "TransactionRecord",
    "ViewBase",
    "address_decoder",
    "all_enables",
    "bitfield",
    "bitfield_set",
    # bits
    "byte_count",
    "check_address_range",
    "check_alignment",
    "check_multiple_of",
    # params
    "check_positive_int",
    "check_power_of_two",
    "check_range",
    "check_signal_direction",
    "check_signal_type",
    "check_signal_width",
    "connect",
    "enable_width",
    "extend_bus_status",
    "get_preset",
    "list_presets",
    "register_preset",
]
