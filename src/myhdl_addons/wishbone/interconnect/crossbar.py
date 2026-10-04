"""Crossbar interconnect (planned — v0.2).

``WB-FR-042`` calls for a crossbar supporting concurrent master<->slave
pairs with per-slave arbitration.  This class reserves the extension point
and the strategy name; the implementation lands in a follow-up increment
(milestone M4).  Subclass :class:`~myhdl_addons.wishbone.interconnect.base.
InterconnectBase` directly if you need a custom concurrent fabric now.
"""

from typing import Any

from ..checks import WishboneConfigError
from .base import InterconnectBase, InterconnectContext

__all__ = ["Crossbar"]


class Crossbar(InterconnectBase):
    """Placeholder for the crossbar strategy (not yet implemented)."""

    name = "crossbar"

    def build(self, ctx: InterconnectContext) -> Any:
        raise WishboneConfigError(
            "Crossbar is not implemented yet (planned for v0.2); "
            "use SharedBus or a custom InterconnectBase subclass"
        )
