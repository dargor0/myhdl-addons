"""RISC-V RV32IC core library (``myhdl_addons.riscv``).

A small, readable, synthesizable RV32I + C (compressed) core assembled from
the independent :mod:`myhdl_addons.components` library and integrated with the
:mod:`myhdl_addons.bus_common` / :mod:`myhdl_addons.wishbone` /
:mod:`myhdl_addons.axi` bus layers.

Every access is dispatched by an **address-region map** to an internal
on-chip memory or to a named external bus.  :class:`CoreConfig` (a
:class:`configparser.ConfigParser` subclass) is the single configuration
object: scalars via the standard ``get*`` methods, derived data via the
``regions``/``buses``/``extensions``/``isa_string``/``misa`` properties, and
boundary checks via ``validate()``.  The RTL blocks and the assembled
``RiscvCore`` are added incrementally.
"""

from .config import (
    AVAIL_ACCESS,
    AVAIL_BASES,
    AVAIL_BUS_TYPES,
    AVAIL_EXTENSIONS,
    AVAIL_FETCH_BUFFER,
    AVAIL_INIT_FIT,
    AVAIL_INIT_FORMATS,
    AVAIL_PERMS,
    AVAIL_PIPELINE_STAGES,
    MISA_BITS,
    CoreConfig,
)
from .branch import AVAIL_BRANCH_OPS, BranchUnit, jalr_target
from .decoder import InstructionDecoder
from .errors import RiscvConfigError, RiscvError, RiscvTypeError
from .extensions import Extension, ExtensionRegistry
from .immgen import AVAIL_IMM_TYPES, ImmGen
from .lsu import LoadStoreUnit
from .pc import ProgramCounter
from .rvc import (
    CExtension,
    RvcDecompressor,
    decompress,
    default_registry,
    is_compressed,
)
from .tohost import ToHost

__all__ = [
    "AVAIL_ACCESS",
    "AVAIL_BASES",
    "AVAIL_BRANCH_OPS",
    "AVAIL_BUS_TYPES",
    "AVAIL_EXTENSIONS",
    "AVAIL_FETCH_BUFFER",
    "AVAIL_IMM_TYPES",
    "AVAIL_INIT_FIT",
    "AVAIL_INIT_FORMATS",
    "AVAIL_PERMS",
    "AVAIL_PIPELINE_STAGES",
    "MISA_BITS",
    "BranchUnit",
    "CExtension",
    "CoreConfig",
    "Extension",
    "ExtensionRegistry",
    "ImmGen",
    "InstructionDecoder",
    "LoadStoreUnit",
    "ProgramCounter",
    "RiscvConfigError",
    "RiscvError",
    "RiscvTypeError",
    "RvcDecompressor",
    "ToHost",
    "decompress",
    "default_registry",
    "is_compressed",
    "jalr_target",
]
