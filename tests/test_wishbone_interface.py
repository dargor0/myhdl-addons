"""Wishbone container / port / view tests (WB-FR-001..010)."""

import pytest
from myhdl import Signal

from myhdl_addons.wishbone import PointToPoint, Wishbone
from myhdl_addons.wishbone.checks import WishboneConfigError


def _bus(**kw):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    return Wishbone(clk, rst, interconnect=PointToPoint(), **kw)


def test_views_and_geometry():
    bus = _bus(data_width=32, adr_width=16, gran=8)
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x00, size=0x100, name="s0")

    assert m.clk is bus.clk and m.rst is bus.rst
    assert s.clk is bus.clk and s.rst is bus.rst
    assert s.base == 0x00 and s.size == 0x100
    assert len(m.adr_o) == 16
    assert len(m.dat_o) == 32
    assert len(m.sel_o) == bus.sel_width == 4
    # within a view the directional names alias the port's signals
    assert m.cyc_o is m._port.cyc and m.ack_i is m._port.ack
    assert s.cyc_i is s._port.cyc and s.ack_o is s._port.ack
    # master and slave ports are distinct signal sets, wired by the fabric
    assert m.cyc_o is not s.cyc_i


def test_optional_signals_disabled_by_default():
    bus = _bus()
    m = bus.add_master("m0")
    assert m.err_i is None
    assert m.rty_i is None
    assert m.lock_o is None


def test_optional_signals_enabled():
    bus = _bus(err=True, rty=True, lock=True)
    m = bus.add_master("m0")
    assert m.err_i is not None
    assert m.rty_i is not None
    assert m.lock_o is not None


def test_cannot_add_port_after_build():
    bus = _bus()
    bus.add_master("m0")
    bus.add_slave(base=0, size=0x100)
    bus.build()
    with pytest.raises(RuntimeError):
        bus.add_master("late")


def test_build_requires_ports():
    bus = _bus()
    with pytest.raises(RuntimeError):
        bus.build()


def test_bad_slave_window():
    bus = _bus(adr_width=8)
    bus.add_master("m0")
    with pytest.raises(WishboneConfigError):
        bus.add_slave(base=0xF0, size=0x20, name="too_big")


def test_slave_requires_size():
    bus = _bus()
    bus.add_master("m0")
    with pytest.raises(WishboneConfigError):
        bus.add_slave(base=0x00)


def test_default_interconnect_builds():
    # no interconnect given -> the container defaults to a shared bus
    bus = Wishbone(
        Signal(bool(0)), Signal(bool(0)), data_width=32, adr_width=16, gran=8
    )
    bus.add_master("m0")
    bus.add_slave(base=0x0000, size=0x10)
    insts = bus.build()
    assert insts


def test_build_rejects_bad_interconnect():
    bus = Wishbone(Signal(bool(0)), Signal(bool(0)))
    bus.add_master("m0")
    bus.add_slave(base=0x0000, size=0x10)
    with pytest.raises(TypeError):
        bus.build(interconnect=object())


def test_repr_and_trace_property():
    bus = _bus(trace=True)
    m = bus.add_master("m0")
    s = bus.add_slave(base=0x0000, size=0x10, name="s0")
    assert "m0" in repr(m)
    assert "s0" in repr(s)
    assert bus.trace.enabled is True
