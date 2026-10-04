"""AXI simulation/debug hooks (re-exported from the common layer, ``AX-FR-130..134``).

AXI does not define a bespoke hook system (``CB-FR-112``); it reuses
:class:`~myhdl_addons.bus_common.Trace` and the shared records, attaching AXI
signals/events from the container and BFMs.
"""

from __future__ import annotations

from ..bus_common import (
    ContentionEvent,
    ErrorEvent,
    Trace,
    TransactionRecord,
)

__all__ = ["ContentionEvent", "ErrorEvent", "Trace", "TransactionRecord"]
