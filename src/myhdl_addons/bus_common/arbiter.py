"""Protocol-agnostic arbiters.

Implements ``CB-FR-050`` (``ArbiterBase`` plus fixed-priority and round-robin
strategies operating on request/grant ``Signal(bool)`` lists), ``CB-FR-051``
(at most one grant per cycle; starvation-free round-robin) and ``CB-FR-052``
(reused by every per-bus fabric).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from myhdl import Signal, SignalType, always, always_comb, block, intbv

from .errors import BusConfigError

__all__ = [
    "ArbiterBase",
    "FixedPriorityArbiter",
    "RoundRobinArbiter",
    "fixed_priority_arbiter",
    "round_robin_arbiter",
]


class ArbiterBase(ABC):
    """Interface implemented by arbiter strategies."""

    @abstractmethod
    def block(
        self,
        clk: SignalType | None,
        rst: SignalType | None,
        requests: Sequence[SignalType],
        grants: Sequence[SignalType],
    ) -> Any:
        """Return MyHDL instances implementing the arbitration."""


@block
def fixed_priority_arbiter_single(req, grant):
    """Only-requester case: ``grant = req``."""

    @always_comb
    def p():
        grant.next = req

    return p


@block
def fixed_priority_arbiter_first(req, grant, higher):
    """First fixed-priority stage: grant ``req`` and record it as higher."""

    @always_comb
    def p():
        grant.next = req
        higher.next = req

    return p


@block
def fixed_priority_arbiter_stage(req, higher, grant, higher_next):
    """A middle fixed-priority stage: grant unless a higher-priority req won."""

    @always_comb
    def p():
        grant.next = req and (not higher)
        higher_next.next = higher or req

    return p


@block
def fixed_priority_arbiter_last(req, higher, grant):
    """Last fixed-priority stage: grant unless a higher-priority request won."""

    @always_comb
    def p():
        grant.next = req and (not higher)

    return p


@block
def fixed_priority_arbiter(
    requests: Sequence[SignalType], grants: Sequence[SignalType]
):
    """Combinational fixed-priority (lowest index wins) arbiter.

    Built as a chain of per-request stages over **individual** signals (a
    list-of-signals indexed inside a process is converted by MyHDL to an
    invalid, continuously-assigned Verilog memory).
    """
    n = len(requests)
    if n != len(grants):
        raise BusConfigError("requests and grants must have equal length")
    if n == 0:
        raise BusConfigError("arbiter needs at least one requester")

    proclist = []
    higher = None
    for i in range(n):
        if i == n - 1:
            if i == 0:
                proclist.append(
                    fixed_priority_arbiter_single(requests[i], grants[i])
                )
            else:
                proclist.append(
                    fixed_priority_arbiter_last(requests[i], higher, grants[i])
                )
        else:
            higher_next = Signal(bool(0))
            if i == 0:
                proclist.append(
                    fixed_priority_arbiter_first(requests[i], grants[i], higher_next)
                )
            else:
                proclist.append(
                    fixed_priority_arbiter_stage(
                        requests[i], higher, grants[i], higher_next
                    )
                )
            higher = higher_next
    return proclist


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


@block
def round_robin_arbiter(
    clk: SignalType | None,
    rst: SignalType | None,
    requests: Sequence[SignalType],
    grants: Sequence[SignalType],
    reset_active: int | None = 1,
):
    """Registered round-robin arbiter with a rotating priority pointer.

    *reset_active* selects the asserted level of *rst*; pass ``None`` to
    ignore the reset entirely (the common layer does not assume a polarity).
    """
    n = len(requests)
    if n != len(grants):
        raise BusConfigError("requests and grants must have equal length")
    if n == 0:
        raise BusConfigError("arbiter needs at least one requester")

    ptr = Signal(intbv(0, min=0, max=n))

    # NOTE: reset handling is selected at elaboration so no free-form
    # ``reset_active is not None`` test reaches the converter.
    if reset_active is None:

        @always(clk.posedge)
        def logic():
            granted = False
            for i in range(n):
                idx = (ptr + i) % n
                if requests[idx] and (not granted):
                    grants[idx].next = 1
                    granted = True
                    ptr.next = (idx + 1) % n
                else:
                    grants[idx].next = 0

    else:

        @always(clk.posedge)
        def logic():
            if rst == reset_active:
                ptr.next = 0
                for i in range(n):
                    grants[i].next = 0
            else:
                granted = False
                for i in range(n):
                    idx = (ptr + i) % n
                    if requests[idx] and (not granted):
                        grants[idx].next = 1
                        granted = True
                        ptr.next = (idx + 1) % n
                    else:
                        grants[idx].next = 0

    return logic


class RoundRobinArbiter(ArbiterBase):
    """Starvation-free round-robin arbiter strategy."""

    def __init__(self, reset_active: int | None = 1) -> None:
        self.reset_active = reset_active

    @block
    def block(
        self,
        clk: SignalType | None,
        rst: SignalType | None,
        requests: Sequence[SignalType],
        grants: Sequence[SignalType],
    ):
        return round_robin_arbiter(clk, rst, requests, grants, self.reset_active)
