"""Port and directional-view base classes (CB-FR-020..023)."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons.bus_common.errors import BusConfigError
from myhdl_addons.bus_common.port import PortBase, ViewBase


def test_port_base():
    port = PortBase("m0", clk="c", rst="r", data_width=32)
    sig = port.add("cyc", "SIG")
    assert sig == "SIG"
    assert port.signal("cyc") == "SIG"
    assert port.signal("missing") is None
    assert port.signals == {"cyc": "SIG"}
    assert port.geometry == {"data_width": 32}
    assert port["cyc"] == "SIG"
    assert "cyc" in port
    assert list(port) == ["cyc"]
    assert "PortBase" in repr(port)


def test_view_base_aliases():
    port = PortBase("m0")
    port.cyc = Signal(bool(0))
    port.adr = port.add("adr", Signal(intbv(0)[4:]))

    view = ViewBase(port, "CLK", "RST")
    assert view.clk == "CLK"
    assert view.rst == "RST"
    assert view.port is port
    assert view.geometry == {}

    view.alias("cyc_o", "cyc")
    assert view.cyc_o is port.cyc
    view.alias_direction("adr", "out", "adr")
    assert view.adr_o is port.adr

    value = view.alias("miss_o", "missing", default="D")
    assert value == "D"
    assert view.miss_o == "D"

    with pytest.raises(BusConfigError):
        view.alias_direction("x", "sideways", "x")

    view.clk = "C2"
    view.rst = "R2"
    assert view.clk == "C2"
    assert view.rst == "R2"
    assert "ViewBase" in repr(view)


def test_view_base_inherits_port_clk_rst():
    port = PortBase("s0", clk="pc", rst="pr")
    view = ViewBase(port)
    assert view.clk == "pc"
    assert view.rst == "pr"
