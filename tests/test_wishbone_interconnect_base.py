"""Base interconnect / context tests and the crossbar placeholder."""

import pytest
from myhdl import Signal

from myhdl_addons.wishbone import Crossbar, Wishbone
from myhdl_addons.wishbone.checks import WishboneConfigError
from myhdl_addons.wishbone.interconnect.base import (
    InterconnectBase,
    InterconnectContext,
)


def test_interconnect_base_is_abstract():
    with pytest.raises(NotImplementedError):
        InterconnectBase().build(None)


def test_interconnect_context():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(
        clk, rst, data_width=32, adr_width=16, gran=8, err=True, rty=True, lock=True
    )
    bus.add_master("m0")
    bus.add_slave(base=0x0000, size=0x100, name="s0")

    ctx = InterconnectContext(bus)
    assert ctx.bus is bus
    assert ctx.clk is clk and ctx.rst is rst
    assert len(ctx.masters) == 1 and len(ctx.slaves) == 1
    assert ctx.data_width == 32
    assert ctx.adr_width == 16
    assert ctx.sel_width == 4
    assert ctx.err and ctx.rty and ctx.lock


def test_crossbar_placeholder_raises():
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    bus = Wishbone(clk, rst)
    bus.add_master("m0")
    bus.add_slave(base=0x0000, size=0x10)
    with pytest.raises(WishboneConfigError):
        Crossbar().build(InterconnectContext(bus))
