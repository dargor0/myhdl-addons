"""Interconnect strategy base and fabric helpers (CB-FR-040..043)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance, intbv

from myhdl_addons.bus_common.addrmap import AddressMap
from myhdl_addons.bus_common.arbiter import FixedPriorityArbiter
from myhdl_addons.bus_common.errors import BusConfigError
from myhdl_addons.bus_common.interconnect import (
    InterconnectBase,
    InterconnectContext,
    arbiter_block,
    decoder_block,
)


def test_context_defaults_from_bus():
    class _Bus:
        clk = "c"
        rst = "r"
        data_width = 32
        adr_width = 16
        gran = 8

    ctx = InterconnectContext(_Bus(), [1], [2], address_map="am")
    assert ctx.clk == "c"
    assert ctx.rst == "r"
    assert ctx.data_width == 32
    assert ctx.adr_width == 16
    assert ctx.gran == 8
    assert ctx.geometry() == {"data_width": 32, "adr_width": 16, "gran": 8}
    assert ctx.masters == [1]
    assert ctx.slaves == [2]
    assert ctx.flags == {}


def test_context_explicit_overrides():
    ctx = InterconnectContext(
        clk="C", rst="R", data_width=8, adr_width=4, gran=8, flags={"err": True}
    )
    assert ctx.clk == "C" and ctx.rst == "R"
    assert ctx.data_width == 8 and ctx.adr_width == 4
    assert ctx.flags == {"err": True}
    assert ctx.bus is None


def test_interconnect_base_is_abstract():
    with pytest.raises(TypeError):
        InterconnectBase()


def test_custom_strategy_and_validate():
    class _Strategy(InterconnectBase):
        name = "custom"

        def build(self, ctx):
            self.validate(ctx)
            return []

    strategy = _Strategy()
    assert strategy.validate(InterconnectContext()) is None
    assert strategy.build(InterconnectContext()) == []


@block
def _fabric_tb():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    adr = Signal(intbv(0)[8:])
    reqs = [Signal(bool(0)) for _ in range(2)]
    grants = [Signal(bool(0)) for _ in range(2)]
    selects = [Signal(bool(0)) for _ in range(2)]

    amap = AddressMap(8)
    amap.add(0x00, 0x10, "a")
    amap.add(0x10, 0x10, "b")

    arb = arbiter_block(FixedPriorityArbiter(), clk, rst, reqs, grants)
    dec = decoder_block(amap, adr, selects)

    @instance
    def stim():
        reqs[0].next = 1
        adr.next = 0x05
        yield delay(1)
        assert grants[0] == 1 and grants[1] == 0
        assert selects[0] == 1 and selects[1] == 0
        adr.next = 0x15
        yield delay(1)
        assert selects[1] == 1 and selects[0] == 0
        raise StopSimulation

    return arb, dec, stim


def test_fabric_helpers_simulate():
    _fabric_tb().run_sim()


def test_decoder_block_length_mismatch():
    amap = AddressMap(8)
    amap.add(0x00, 0x10, "a")
    with pytest.raises(BusConfigError):
        decoder_block(amap, Signal(intbv(0)[8:]), [])
