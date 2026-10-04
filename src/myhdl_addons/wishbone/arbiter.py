"""Wishbone arbiters.

Implements ``WB-FR-050`` (parameterisable arbiter; fixed-priority provided
in this initial increment, round-robin is a follow-up), ``WB-FR-052``
(one grant per cycle) and ``WB-FR-053`` (per-requester grant visibility).

An arbiter is a small MyHDL block operating on a list of request signals
and a list of one-hot grant signals.  Custom arbiters may be supplied to
the shared-bus interconnect by subclassing :class:`ArbiterBase`.
"""

from collections.abc import Sequence
from typing import Any

from myhdl import SignalType, block

from ..bus_common.arbiter import fixed_priority_arbiter as _common_fixed_priority
from .checks import WishboneConfigError

__all__ = ["ArbiterBase", "FixedPriorityArbiter", "fixed_priority_arbiter"]


class ArbiterBase:
    """Interface implemented by arbiter strategies."""

    def block(
        self,
        clk: SignalType | None,
        rst: SignalType | None,
        requests: Sequence[SignalType],
        grants: Sequence[SignalType],
    ) -> Any:
        """Return MyHDL instances implementing the arbitration."""
        raise NotImplementedError


@block
def fixed_priority_arbiter(
    requests: Sequence[SignalType], grants: Sequence[SignalType]
):
    """Combinational fixed-priority (lowest index wins) arbiter.

    Thin Wishbone wrapper around the common
    :func:`~myhdl_addons.bus_common.arbiter.fixed_priority_arbiter`; it keeps
    the Wishbone error type for the argument validation.  Only one grant is
    asserted per evaluation (``WB-FR-052``).
    """
    if len(requests) != len(grants):
        raise WishboneConfigError("requests and grants must have equal length")
    if len(requests) == 0:
        raise WishboneConfigError("arbiter needs at least one requester")
    return _common_fixed_priority(requests, grants)


class FixedPriorityArbiter(ArbiterBase):
    """Fixed-priority arbiter strategy (lowest index = highest priority)."""

    @block
    def block(
        self,
        clk: SignalType | None,
        rst: SignalType | None,
        requests: Sequence[SignalType],
        grants: Sequence[SignalType],
    ):
        return fixed_priority_arbiter(requests, grants)
