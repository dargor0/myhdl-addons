"""Incrementer configuration and registered output (``IC-FR-046..048``)."""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import HdlConfigError, Incrementer


def test_step_sel_omitted_for_single_step():
    assert "step_sel" not in Incrementer(steps=(1,)).ports().names


def test_step_sel_present_for_multiple_steps():
    ports = Incrementer(steps=(2, 4, -2, -4)).ports()
    assert "step_sel" in ports.names


def test_load_disabled_omits_ports():
    ports = Incrementer(load_enable=False).ports()
    assert "load" not in ports.names
    assert "load_value" not in ports.names


def test_as_dict():
    inc = Incrementer(width=16, steps=(1, -1), carry=True)
    info = inc.as_dict()
    assert info["width"] == 16
    assert info["steps"] == (1, -1)
    assert info["carry"] is True
    assert "Incrementer" in repr(inc)


@block
def _reg_tb(results):
    inc = Incrementer(width=8, steps=(1,), registered=1)
    ports = inc.ports()
    dut = inc.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 1
        ports.en.next = 1
        ports.a.next = 9
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.reset.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return clkgen, dut, stim


def test_registered_incrementer():
    results = []
    _reg_tb(results).run_sim()
    assert results == [0, 10]


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        Incrementer(steps=[])


def test_configuration_matrix():
    for component in (
        Incrementer(width=8, steps=(1,), load_enable=False),
        Incrementer(
            width=8,
            steps=(2, 4, -2, -4),
            wrap_mode="saturate",
            carry=True,
            registered=1,
        ),
    ):
        assert component.hdl(component.ports()) is not None
