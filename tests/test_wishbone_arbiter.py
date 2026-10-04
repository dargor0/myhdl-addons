"""Arbiter tests (WB-FR-050/052/053)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance

from myhdl_addons.wishbone.arbiter import (
    ArbiterBase,
    FixedPriorityArbiter,
    fixed_priority_arbiter,
)
from myhdl_addons.wishbone.checks import WishboneConfigError


def test_arbiter_length_mismatch():
    requests = [Signal(bool(0))]
    grants = []
    with pytest.raises(WishboneConfigError):
        fixed_priority_arbiter(requests, grants)


def test_arbiter_needs_requesters():
    with pytest.raises(WishboneConfigError):
        fixed_priority_arbiter([], [])


def test_arbiter_base_not_implemented():
    with pytest.raises(NotImplementedError):
        ArbiterBase().block(None, None, [], [])


@block
def _arbiter_tb():
    requests = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = FixedPriorityArbiter().block(None, None, requests, grants)

    @instance
    def stim():
        yield delay(1)
        assert [int(g) for g in grants] == [0, 0, 0]

        requests[0].next = 1
        requests[2].next = 1
        yield delay(1)
        assert [int(g) for g in grants] == [1, 0, 0]  # lowest index wins

        requests[0].next = 0
        yield delay(1)
        assert [int(g) for g in grants] == [0, 0, 1]

        requests[1].next = 1
        yield delay(1)
        assert [int(g) for g in grants] == [0, 1, 0]
        raise StopSimulation

    return arb, stim


def test_fixed_priority_arbiter_sim():
    _arbiter_tb().run_sim()
