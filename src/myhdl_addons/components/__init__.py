"""Independent, configurable component library (``myhdl_addons.components``).

ISA-neutral, bus-agnostic hardware building blocks used by the RISC-V core
and other designs.  See ``reqs/07_independent_components.md``.  External
runtime dependencies are limited to ``myhdl``; shared code (errors, config
helpers, :class:`SignalView`) comes from :mod:`myhdl_addons.common`.

Most components expose their ports through a :class:`SignalView`
(``IC-FR-145``) and their effective configuration through ``as_dict()``
(``IC-FR-122``); the structural :func:`output_stage` block drives signal
bundles directly (see its module docstring).
"""

from ..common.config import ComponentBase
from ..common.errors import HdlConfigError, HdlError
from ..common.views import SignalView, connect
from .alu import (
    AVAIL_FLAGS,
    AVAIL_OPS,
    Alu,
)
from .comparator import AVAIL_OUTPUTS, Comparator
from .counter import Counter, CounterPorts
from .encoder import (
    PRIORITIES,
    Decoder,
    DecoderPorts,
    PriorityEncoder,
    PriorityEncoderPorts,
)
from .fifo import (
    INTERFACES,
    STREAM,
    WR_RD,
    Fifo,
    FifoPorts,
)
from .incrementer import WRAP_MODES, Incrementer, IncrementerPorts
from .memory import SyncRam, SyncRamPorts, SyncRom, SyncRomPorts
from .mux import Mux, MuxPorts, OneHotMux, OneHotMuxPorts
from .output_stage import output_stage
from .regfile import (
    NO_CHANGE,
    READ_FIRST,
    WRITE_FIRST,
    WRITE_MODES,
    RegisterFile,
    RegisterFilePorts,
)
from .register import Register, RegisterPorts
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
    BarrelShifterPorts,
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
    "Alu",
    "BarrelShifter",
    "BarrelShifterPorts",
    "Comparator",
    "ComponentBase",
    "Counter",
    "CounterPorts",
    "Decoder",
    "DecoderPorts",
    "Fifo",
    "FifoPorts",
    "HdlConfigError",
    "HdlError",
    "Incrementer",
    "IncrementerPorts",
    "Mux",
    "MuxPorts",
    "OneHotMux",
    "OneHotMuxPorts",
    "PriorityEncoder",
    "PriorityEncoderPorts",
    "Register",
    "RegisterFile",
    "RegisterFilePorts",
    "RegisterPorts",
    "SignalView",
    "SyncRam",
    "SyncRamPorts",
    "SyncRom",
    "SyncRomPorts",
    "connect",
    "output_stage",
]
