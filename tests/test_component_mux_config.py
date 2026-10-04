"""Mux configuration and registered output (``IC-FR-061..063``)."""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import HdlConfigError, Mux


def test_as_dict():
    mux = Mux(width=8, n=3, default_value=0xAA, valid=True)
    info = mux.as_dict()
    assert info["width"] == 8
    assert info["n"] == 3
    assert info["default_value"] == 0xAA
    assert info["valid"] is True
    assert info["registered"] is False
    assert "Mux" in repr(mux)


def test_combinational_has_no_clock():
    names = Mux(width=8, n=3).ports().names
    assert "clk" not in names
    assert "reset" not in names


def test_registered_ports():
    names = Mux(width=8, n=3, valid=True, registered=True, en=True).ports().names
    assert {"clk", "reset", "en", "valid"}.issubset(names)


@block
def _reg_tb(results):
    mux = Mux(width=8, n=2, valid=True, registered=True, en=True, reset_value=0x77)
    ports = mux.ports()
    dut = mux.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.in0.next = 0xAA
        ports.in1.next = 0xBB
        ports.sel.next = 0
        ports.reset.next = 0  # assert reset
        ports.en.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.valid)))
        ports.reset.next = 1  # release
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.valid)))
        ports.sel.next = 1
        ports.en.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.valid)))
        raise StopSimulation

    return clkgen, dut, stim


def test_registered_reset_capture_and_enable():
    results = []
    _reg_tb(results).run_sim()
    assert results == [(0x77, 0), (0xAA, 1), (0xAA, 1)]


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        Mux(width=8, n=0)


def test_configuration_matrix():
    for component in (
        Mux(width=8, n=1, valid=True),
        Mux(width=8, n=5, default_value=0xFF, registered=1, en=True),
    ):
        assert component.hdl(component.ports()) is not None
