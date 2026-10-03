"""Independent, configurable component library (``myhdl_addons.components``).

ISA-neutral, bus-agnostic hardware building blocks used by the RISC-V core
and other designs.  See ``reqs/07_independent_components.md``.  External
runtime dependencies are limited to ``myhdl``; shared code (errors, config
helpers, :class:`SignalView`) comes from :mod:`myhdl_addons.common`.

Most components expose their ports through a :class:`SignalView`
(``IC-FR-145``) and their effective configuration through ``as_dict()``
(``IC-FR-122``).
"""

from ..common.config import ComponentBase
from ..common.errors import HdlConfigError, HdlError
from ..common.views import SignalView, connect
from .address_decoder import AddressDecoder
from .alu import (
    AVAIL_FLAGS,
    AVAIL_OPS,
    Alu,
)
from .comparator import AVAIL_OUTPUTS, Comparator
from .counter import Counter
from .encoder import (
    PRIORITIES,
    Decoder,
    PriorityEncoder,
)
from .fifo import (
    INTERFACES,
    STREAM,
    WR_RD,
    Fifo,
)
from .incrementer import WRAP_MODES, Incrementer
from .memory import SyncRam, SyncRom
from .mux import Mux, OneHotMux
from .regfile import (
    NO_CHANGE,
    READ_FIRST,
    WRITE_FIRST,
    WRITE_MODES,
    RegisterFile,
)
from .register import Register
from .shifter import (
    MODE_NAMES,
    MODES,
    ROL,
    ROR,
    SLL,
    SRA,
    SRL,
    STRUCTURES,
    BarrelShifter,
)

__all__ = [
    "AVAIL_FLAGS",
    "AVAIL_OPS",
    "AVAIL_OUTPUTS",
    "INTERFACES",
    "MODES",
    "MODE_NAMES",
    "NO_CHANGE",
    "OP_NAMES",
    "PRIORITIES",
    "READ_FIRST",
    "ROL",
    "ROR",
    "SLL",
    "SRA",
    "SRL",
    "STREAM",
    "STRUCTURES",
    "WRAP_MODES",
    "WRITE_FIRST",
    "WRITE_MODES",
    "WR_RD",
    "AddressDecoder",
    "Alu",
    "BarrelShifter",
    "Comparator",
    "ComponentBase",
    "Counter",
    "Decoder",
    "Fifo",
    "HdlConfigError",
    "HdlError",
    "Incrementer",
    "Mux",
    "OneHotMux",
    "PriorityEncoder",
    "Register",
    "RegisterFile",
    "SignalView",
    "SyncRam",
    "SyncRom",
    "connect",
]
