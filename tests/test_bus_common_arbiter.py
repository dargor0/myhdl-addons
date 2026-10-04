"""Common arbiter strategies (CB-FR-050..052)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance

from myhdl_addons.bus_common.arbiter import (
    FixedPriorityArbiter,
    RoundRobinArbiter,
    fixed_priority_arbiter,
    round_robin_arbiter,
)
from myhdl_addons.bus_common.errors import BusConfigError


@block
def _fixed_tb():
    reqs = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = FixedPriorityArbiter().block(None, None, reqs, grants)

    @instance
    def stim():
        reqs[0].next = 1
        reqs[2].next = 1
        yield delay(1)
        assert [int(g) for g in grants] == [1, 0, 0]
        reqs[0].next = 0
        yield delay(1)
        assert [int(g) for g in grants] == [0, 0, 1]
        reqs[2].next = 0
        yield delay(1)
        assert [int(g) for g in grants] == [0, 0, 0]
        raise StopSimulation

    return arb, stim


def test_fixed_priority():
    _fixed_tb().run_sim()


@block
def _round_robin_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    reqs = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = RoundRobinArbiter().block(clk, rst, reqs, grants)

    @instance
    def stim():
        reqs[0].next = 1
        reqs[1].next = 1
        reqs[2].next = 1
        seen = []
        for _ in range(6):
            clk.next = 1
            yield delay(1)
            seen.append([int(g) for g in grants])
            clk.next = 0
            yield delay(1)
        for row in seen:
            assert sum(row) == 1, row
        winners = [row.index(1) for row in seen]
        assert winners[:3] == [0, 1, 2], winners
        raise StopSimulation

    return arb, stim


def test_round_robin_rotates_and_is_one_hot():
    _round_robin_tb().run_sim()


@block
def _round_robin_reset_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(1))
    reqs = [Signal(bool(0)) for _ in range(2)]
    grants = [Signal(bool(0)) for _ in range(2)]
    arb = round_robin_arbiter(clk, rst, reqs, grants, reset_active=1)

    @instance
    def stim():
        reqs[0].next = 1
        reqs[1].next = 1
        clk.next = 1
        yield delay(1)
        assert [int(g) for g in grants] == [0, 0]
        rst.next = 0
        clk.next = 0
        yield delay(1)
        clk.next = 1
        yield delay(1)
        assert sum(int(g) for g in grants) == 1
        raise StopSimulation

    return arb, stim


def test_round_robin_reset():
    _round_robin_reset_tb().run_sim()


@block
def _round_robin_no_reset_tb():
    clk = Signal(bool(0))
    reqs = [Signal(bool(0)) for _ in range(2)]
    grants = [Signal(bool(0)) for _ in range(2)]
    arb = round_robin_arbiter(clk, None, reqs, grants, reset_active=None)

    @instance
    def stim():
        reqs[1].next = 1
        clk.next = 1
        yield delay(1)
        assert sum(int(g) for g in grants) == 1
        raise StopSimulation

    return arb, stim


def test_round_robin_ignores_reset_when_none():
    _round_robin_no_reset_tb().run_sim()


def test_arbiter_length_and_empty_validation():
    with pytest.raises(BusConfigError):
        fixed_priority_arbiter([Signal(bool(0))], [Signal(bool(0)), Signal(bool(0))])
    with pytest.raises(BusConfigError):
        fixed_priority_arbiter([], [])
    with pytest.raises(BusConfigError):
        round_robin_arbiter(
            None, None, [Signal(bool(0))], [Signal(bool(0)), Signal(bool(0))]
        )
    with pytest.raises(BusConfigError):
        round_robin_arbiter(None, None, [], [])


def test_round_robin_constructor():
    assert RoundRobinArbiter(reset_active=0).reset_active == 0
