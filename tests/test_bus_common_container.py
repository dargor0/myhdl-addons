"""Common bus container base (CB-FR-030..033)."""

import pytest
from myhdl import Signal

from myhdl_addons.bus_common.container import BusContainerBase
from myhdl_addons.bus_common.errors import BusConfigError
from myhdl_addons.bus_common.interconnect import InterconnectBase
from myhdl_addons.bus_common.port import ViewBase


class _Port:
    def __init__(self, bus, name, base=0, size=None):
        self.bus = bus
        self.name = name
        self.base = base
        self.size = size


class _View:
    def __init__(self, bus, port):
        self.bus = bus
        self.port = port
        self.name = port.name
        self.clk = bus.clk
        self.rst = bus.rst


class _Bus(BusContainerBase):
    port_cls = _Port
    master_view_cls = _View
    slave_view_cls = _View


class _Strategy(InterconnectBase):
    name = "dummy"

    def __init__(self):
        self.built = 0

    def validate(self, ctx):
        assert ctx.masters and ctx.slaves

    def build(self, ctx):
        self.built += 1
        return []


def _bus(**kw):
    return _Bus(Signal(bool(0)), Signal(bool(0)), **kw)


def test_add_ports_and_build():
    bus = _bus()
    master = bus.add_master()
    slave = bus.add_slave(0, 0x100)
    assert bus.masters[0] is master.port
    assert bus.slaves[0] is slave.port
    assert len(bus.address_map) == 1
    assert bus.address_map.bases() == [0]
    metadata = bus.metadata()
    assert metadata["reset_name"] == "rst"
    assert metadata["handshake"] == "generic"
    strategy = _Strategy()
    bus.build(strategy)
    assert strategy.built == 1


def test_build_appends_trace_monitors():
    bus = _bus(trace=True)
    bus.add_master()
    bus.add_slave(0, 0x10)
    bus.trace.signal(Signal(bool(0)), name="cyc")
    assert len(bus.trace._signals) == 1
    assert bus.build(_Strategy()) is not None


def test_build_requires_ports():
    bus = _bus()
    with pytest.raises(BusConfigError):
        bus.build(_Strategy())
    bus.add_master()
    with pytest.raises(BusConfigError):
        bus.build(_Strategy())


def test_build_requires_strategy():
    bus = _bus()
    bus.add_master()
    bus.add_slave(0, 0x10)
    with pytest.raises(BusConfigError):
        bus.build()
    with pytest.raises(BusConfigError):
        bus.build(object())


def test_add_after_build_rejected():
    bus = _bus()
    bus.add_master()
    bus.add_slave(0, 0x10)
    bus.build(_Strategy())
    with pytest.raises(BusConfigError):
        bus.add_master()
    with pytest.raises(BusConfigError):
        bus.add_slave(0x10, 0x10, name="s1")


def test_default_port_and_view_classes():
    bus = BusContainerBase(Signal(bool(0)), Signal(bool(0)))
    master = bus.add_master("m0")
    bus.add_slave(0x10, 0x10)
    assert isinstance(master, ViewBase)
    assert bus.masters[0].name == "m0"


def test_strategy_validation_rejects_topology():
    class _Strict(InterconnectBase):
        def validate(self, ctx):
            if len(ctx.masters) != 1:
                raise BusConfigError("only one master allowed")

        def build(self, ctx):
            return []

    bus = _bus()
    bus.add_master()
    bus.add_master()
    bus.add_slave(0, 0x10)
    with pytest.raises(BusConfigError):
        bus.build(_Strict())


def test_context_provides_geometry():
    bus = _bus(data_width=64, adr_width=24, gran=8)
    bus.add_master()
    bus.add_slave(0, 0x1000)
    ctx = bus.make_context()
    assert ctx.geometry() == {"data_width": 64, "adr_width": 24, "gran": 8}
    assert ctx.address_map is bus.address_map
    assert len(ctx.masters) == 1 and len(ctx.slaves) == 1
