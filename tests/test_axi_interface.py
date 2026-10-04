"""AXI container / ports / views (AX-FR-001..008)."""

import pytest
from myhdl import Signal

from myhdl_addons.axi import Axi, AxiPointToPoint
from myhdl_addons.axi.checks import AxiConfigError


def _bus(**kw):
    return Axi(Signal(bool(0)), Signal(bool(0)), **kw)


def test_lite_signals_and_views():
    bus = _bus(variant="lite", data_width=32, addr_width=32)
    m = bus.add_master("m0")
    assert m.awvalid is m._port.awvalid
    assert len(m.wstrb) == 4
    assert len(m.awaddr) == 32
    assert m.aclk is bus.aclk and m.aresetn is bus.aresetn
    assert m.clk is bus.aclk and m.rst is bus.aresetn


def test_full_signal_widths():
    bus = _bus(variant="full", id_width=6, data_width=64)
    m = bus.add_master()
    assert len(m.awlen) == 8
    assert len(m.awsize) == 3
    assert len(m.awburst) == 2
    assert len(m.awid) == 6
    assert len(m.wstrb) == 8
    assert m.wlast is not None and m.rlast is not None


def test_stream_signals():
    bus = _bus(variant="stream", data_width=32)
    m = bus.add_master()
    assert m.tdata is not None and m.tready is not None


def test_user_sidebands_enabled():
    bus = _bus(variant="full", user=True, user_width=4)
    m = bus.add_master()
    s = bus.add_slave(0, 0x10)
    assert len(m.awuser) == 4
    assert m.awqos is not None
    assert s.buser is not None


def test_user_sidebands_lite_disabled():
    bus = _bus(variant="lite", user=True)
    m = bus.add_master()
    assert not hasattr(m, "awuser")


def test_build_ok_full():
    bus = _bus(variant="full")
    bus.add_master()
    bus.add_slave(0, 0x100)
    assert bus.build(AxiPointToPoint()) is not None


def test_add_after_build_rejected():
    bus = _bus(variant="lite")
    bus.add_master()
    bus.add_slave(0, 0x100)
    bus.build(AxiPointToPoint())
    with pytest.raises(AxiConfigError):
        bus.add_master()
    with pytest.raises(AxiConfigError):
        bus.add_slave(0x100, 0x10)


def test_build_requires_ports():
    bus = _bus(variant="lite")
    with pytest.raises(AxiConfigError):
        bus.build(AxiPointToPoint())
    bus.add_master()
    with pytest.raises(AxiConfigError):
        bus.build(AxiPointToPoint())


def test_build_requires_strategy():
    bus = _bus(variant="lite")
    bus.add_master()
    bus.add_slave(0, 0x10)
    with pytest.raises(AxiConfigError):
        bus.build()
    with pytest.raises(AxiConfigError):
        bus.build(object())


def test_bad_slave_window():
    bus = _bus(variant="lite", addr_width=8)
    bus.add_master()
    with pytest.raises(AxiConfigError):
        bus.add_slave(0xF0, 0x20, name="too_big")
    with pytest.raises(AxiConfigError):
        bus.add_slave(0)


def test_metadata_and_properties():
    bus = _bus(variant="lite")
    md = bus.metadata()
    assert md["reset_name"] == "aresetn"
    assert md["reset_active"] == 0
    assert md["handshake"] == "valid/ready"
    assert bus.masters == [] and bus.slaves == []
    assert bus.address_map is not None
    assert bus.trace is not None


def test_port_lookup_and_repr():
    bus = _bus(variant="lite")
    m = bus.add_master("m0")
    assert m._port.signal("awvalid") is m.awvalid
    with pytest.raises(AxiConfigError):
        m._port.signal("nope")
    assert "m0" in repr(m)
    assert "AxiPort" in repr(m._port)
