"""RISC-V core exception aliases (re-exported from :mod:`myhdl_addons.common`).

The exception classes themselves live in the single shared location
``myhdl_addons.common.errors``; this module only re-exports the RISC-V
aliases so ``from .errors import RiscvConfigError`` works, mirroring the bus
libraries (``RC-FR-008``).
"""

from ..common.errors import RiscvConfigError, RiscvError, RiscvTypeError

__all__ = ["RiscvConfigError", "RiscvError", "RiscvTypeError"]
