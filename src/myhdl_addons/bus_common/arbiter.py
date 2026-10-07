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
                proclist.append(fixed_priority_arbiter_single(requests[i], grants[i]))
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
def rr_gated_ge(req, ptr, index, out):
    """Rotation gate: ``out = req and (ptr <= index)`` (at/after the pointer)."""

    @always_comb
    def p():
        out.next = req and (ptr <= index)

    return p


@block
def rr_gated_lt(req, ptr, index, out):
    """Rotation gate: ``out = req and (ptr > index)`` (before the pointer)."""

    @always_comb
    def p():
        out.next = req and (ptr > index)

    return p


@block
def rr_grant(hi_win, lo_win, any_hi, out):
    """Grant the high-group winner, else the low-group winner."""

    @always_comb
    def p():
        out.next = hi_win or (lo_win and (not any_hi))

    return p


@block
def rr_next(grant, value, out):
    """One-hot next-pointer contribution: *value* when granted, else ``0``."""

    @always_comb
    def p():
        if grant:
            out.next = value
        else:
            out.next = 0

    return p


@block
def rr_or_first(value, out):
    """First stage of an OR reduction."""

    @always_comb
    def p():
        out.next = value

    return p


@block
def rr_or_stage(value, acc, out):
    """Later stage of an OR reduction."""

    @always_comb
    def p():
        out.next = acc | value

    return p


@block
def rr_output(grant, rst, reset_active, out):
    """Combinational grant output, forced low while reset is asserted.

    Grants are driven combinationally from the registered pointer (not
    captured on the edge): this keeps the winner visible in the same cycle and
    avoids racing the combinational priority decode at the clock edge.
    """

    if reset_active is None:

        @always_comb
        def p():
            out.next = grant

    else:

        @always_comb
        def p():
            if rst == reset_active:
                out.next = 0
            else:
                out.next = grant

    return p


@block
def rr_reg_ptr(clk, rst, reset_active, any_grant, ptr_next, q):
    """Registered rotating pointer; holds when no request is granted."""

    if reset_active is None:

        @always(clk.posedge)
        def p():
            if any_grant:
                q.next = ptr_next

    else:

        @always(clk.posedge)
        def p():
            if rst == reset_active:
                q.next = 0
            elif any_grant:
                q.next = ptr_next

    return p


@block
def round_robin_arbiter(
    clk: SignalType | None,
    rst: SignalType | None,
    requests: Sequence[SignalType],
    grants: Sequence[SignalType],
    reset_active: int | None = 1,
):
    """Registered round-robin arbiter with a rotating priority pointer.

    Convertible by construction: the rotation gates, the two priority chains
    and the pointer update are elaborated **per requester over individual
    signals**, so no list-of-signals is ever indexed inside a process.

    *reset_active* selects the asserted level of *rst*; pass ``None`` to
    ignore the reset entirely (the common layer does not assume a polarity).
    """
    n = len(requests)
    if n != len(grants):
        raise BusConfigError("requests and grants must have equal length")
    if n == 0:
        raise BusConfigError("arbiter needs at least one requester")

    ptr = Signal(intbv(0, min=0, max=n))
    procs = []

    # Split the requests into the "at/after the pointer" and "before the
    # pointer" rotation groups and run a fixed-priority chain over each.
    hi = [Signal(bool(0)) for _ in range(n)]
    lo = [Signal(bool(0)) for _ in range(n)]
    for i in range(n):
        procs.append(rr_gated_ge(requests[i], ptr, i, hi[i]))
        procs.append(rr_gated_lt(requests[i], ptr, i, lo[i]))

    hi_win = [Signal(bool(0)) for _ in range(n)]
    lo_win = [Signal(bool(0)) for _ in range(n)]
    procs.append(fixed_priority_arbiter(hi, hi_win))
    procs.append(fixed_priority_arbiter(lo, lo_win))

    any_hi = Signal(bool(0))
    acc = None
    for i in range(n):
        dst = any_hi if i == n - 1 else Signal(bool(0))
        procs.append(
            rr_or_first(hi[i], dst) if acc is None else rr_or_stage(hi[i], acc, dst)
        )
        acc = dst

    grant_comb = [Signal(bool(0)) for _ in range(n)]
    for i in range(n):
        procs.append(rr_grant(hi_win[i], lo_win[i], any_hi, grant_comb[i]))

    any_grant = Signal(bool(0))
    acc = None
    for i in range(n):
        dst = any_grant if i == n - 1 else Signal(bool(0))
        procs.append(
            rr_or_first(grant_comb[i], dst)
            if acc is None
            else rr_or_stage(grant_comb[i], acc, dst)
        )
        acc = dst

    next_parts = [Signal(intbv(0, min=0, max=n)) for _ in range(n)]
    for i in range(n):
        procs.append(rr_next(grant_comb[i], (i + 1) % n, next_parts[i]))
    ptr_next = Signal(intbv(0, min=0, max=n))
    acc = None
    for i in range(n):
        dst = ptr_next if i == n - 1 else Signal(intbv(0, min=0, max=n))
        procs.append(
            rr_or_first(next_parts[i], dst)
            if acc is None
            else rr_or_stage(next_parts[i], acc, dst)
        )
        acc = dst

    for i in range(n):
        procs.append(rr_output(grant_comb[i], rst, reset_active, grants[i]))
    procs.append(rr_reg_ptr(clk, rst, reset_active, any_grant, ptr_next, ptr))
    return procs


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
