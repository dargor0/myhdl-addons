"""RISC-V ISA plug-in mechanism (``RC-FR-030..039``).

Extensions are **elaboration-time** objects.  Each declares the 32-bit
encodings it owns (:meth:`Extension.claims` / :meth:`Extension.matches`), the
control values it contributes, the CSRs and reset/front-end/components hooks it
adds.  RTL blocks are handed the **extension context** — a plain
:class:`~myhdl_addons.common.views.SignalView` holding the core ports an
extension may bind to — so an extension never reaches into core internals (Q16).

:class:`ExtensionRegistry` registers the available extensions, selects the
enabled ones (priority order, rejecting conflicts) and builds **only** the
enabled extensions' blocks, so a disabled extension contributes **zero logic**
(``RC-FR-033``).
"""

from collections.abc import Iterable

from myhdl import block

from ..common.errors import RiscvConfigError
from ..common.views import SignalView

__all__ = ["Extension", "ExtensionRegistry"]

_WORD_MASK = 0xFFFF_FFFF


class Extension:
    """Base class for ISA plug-ins (``RC-FR-030`` / Q16).

    A concrete extension sets :attr:`name` (matching its
    ``[extension.<name>]`` config key) and overrides the hooks it needs.
    """

    #: Extension name, matching the ``[extension.<name>]`` INI section.
    name: str = ""
    #: Decode priority: higher wins; ties are broken by name.
    priority: int = 0

    def claims(self) -> tuple[tuple[int, int], ...]:
        """Return ``(mask, value)`` 32-bit encodings this extension owns."""
        return ()

    def matches(self, instruction: int) -> bool:
        """Return whether *instruction* belongs to this extension.

        The default matches against :meth:`claims`; override for non-mask
        decoders (the registry's conflict check uses :meth:`claims`).
        """
        word = instruction & _WORD_MASK
        return any((word & mask) == value for mask, value in self.claims())

    def decode(self, instruction: int) -> dict:
        """Return the control/enum values for a matched instruction."""
        return {}

    def csrs(self) -> tuple[str, ...]:
        """Return the names of the CSRs this extension contributes."""
        return ()

    def front_end(self, context: SignalView) -> list:
        """Return fetch/decompress-stage blocks (``RC-FR-042`` / Q17)."""
        return []

    @block
    def decode_stage(self, context: SignalView) -> list:
        """Return decode-stage blocks for this extension (``RC-FR-056`` / Q16).

        A **decode extension** overrides this (also with ``@block``) and returns
        blocks that drive the control bundle exposed in *context*: ``instr``
        plus every decoder control signal, including ``matched``.  The extension
        MUST drive all of them, setting ``matched`` when it handles the current
        instruction; the decoder selects the highest-priority *matched*
        extension's bundle over the base decode.  The default contributes
        nothing.
        """
        return []

    def components(self, context: SignalView) -> list:
        """Return extra datapath blocks (``RC-FR-030``)."""
        return []

    def reset(self, context: SignalView) -> list:
        """Return reset-hook blocks (``RC-FR-030``)."""
        return []


class ExtensionRegistry:
    """Register ISA plug-ins and build the enabled set (``RC-FR-031..033``)."""

    def __init__(self, available: Iterable[Extension] = ()) -> None:
        self._extensions: dict[str, Extension] = {}
        for extension in available:
            self.register(extension)
        self._selected: tuple[Extension, ...] = ()

    def register(self, extension: Extension) -> None:
        """Add *extension*; a duplicate or empty name raises (``RC-FR-036``)."""
        name = extension.name
        if not isinstance(name, str) or not name:
            raise RiscvConfigError("extension name must be a non-empty string")
        if name in self._extensions:
            raise RiscvConfigError(f"duplicate extension {name!r}")
        self._extensions[name] = extension

    def names(self) -> tuple[str, ...]:
        """Return the registered extension names."""
        return tuple(self._extensions)

    def get(self, name: str) -> Extension:
        """Return the extension called *name*, or raise (``RC-FR-036``)."""
        try:
            return self._extensions[name]
        except KeyError:
            raise RiscvConfigError(f"unknown extension {name!r}") from None

    def select(self, enabled: Iterable[str]) -> tuple[Extension, ...]:
        """Select and order the enabled extensions; reject conflicts."""
        requested = tuple(enabled)
        if len(set(requested)) != len(requested):
            raise RiscvConfigError("duplicate enabled extension")
        chosen = tuple(self.get(name) for name in requested)
        ordered = tuple(sorted(chosen, key=lambda ext: (-ext.priority, ext.name)))
        self._check_conflicts(ordered)
        self._selected = ordered
        return ordered

    @property
    def selected(self) -> tuple[Extension, ...]:
        """Return the currently selected (enabled) extensions."""
        return self._selected

    def is_enabled(self, name: str) -> bool:
        """Return whether extension *name* is currently selected."""
        return any(extension.name == name for extension in self._selected)

    def build(self, context: SignalView) -> list:
        """Return the RTL blocks of the selected extensions (``RC-FR-033``)."""
        blocks: list = []
        for extension in self._selected:
            blocks.extend(extension.front_end(context))
            blocks.extend(extension.components(context))
            blocks.extend(extension.reset(context))
        return blocks

    def _check_conflicts(self, extensions: tuple[Extension, ...]) -> None:
        """Raise if two selected extensions claim overlapping encodings."""
        claims: list[tuple[str, int, int]] = []
        for extension in extensions:
            for mask, value in extension.claims():
                claims.append((extension.name, mask & _WORD_MASK, value & _WORD_MASK))
        for i in range(len(claims)):
            name_i, mask_i, value_i = claims[i]
            for j in range(i + 1, len(claims)):
                name_j, mask_j, value_j = claims[j]
                if name_i == name_j:
                    continue
                if ((value_i ^ value_j) & (mask_i & mask_j)) == 0:
                    raise RiscvConfigError(
                        f"extension conflict: {name_i!r} and {name_j!r} "
                        f"claim overlapping encodings"
                    )
