"""FIFO optional outputs and flush (``IC-FR-116..119``)."""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Fifo, HdlConfigError


@block
def _fifo_tb(results, config, actions):
    fifo = Fifo(**config)
    ports = fifo.ports()
    dut = fifo.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.resetn.next = 0
        yield ports.clk.posedge
        ports.resetn.next = 1
        for action in actions:
            for name, value in action.get("set", {}).items():
                getattr(ports, name).next = value
            if action.get("edge"):
                yield ports.clk.posedge
            yield delay(1)
            if "sample" in action:
                results.append(tuple(int(ports[n]) for n in action["sample"]))
        raise StopSimulation

    return clkgen, dut, stim


def _run(config, actions):
    results = []
    _fifo_tb(results, config, actions).run_sim()
    return results


def test_count_and_thresholds():
    config = {
        "width": 8,
        "depth": 4,
        "fall_through": True,
        "count": True,
        "almost_full": 3,
        "almost_empty": 1,
    }
    actions = [
        {"set": {"wr_en": 1, "wdata": 0x11}, "edge": True},
        {"set": {"wr_en": 1, "wdata": 0x22}, "edge": True},
        {
            "set": {"wr_en": 1, "wdata": 0x33},
            "edge": True,
            "sample": ["count", "almost_full"],
        },
        {"set": {"wr_en": 0, "rd_en": 1}, "edge": True, "sample": ["count"]},
        {"set": {"rd_en": 1}, "edge": True, "sample": ["count", "almost_empty"]},
    ]
    assert _run(config, actions) == [(3, 1), (2,), (1, 1)]


def test_optional_ports_absent_by_default():
    ports = Fifo(width=8, depth=4).ports()
    assert "count" not in ports.names
    assert "almost_full" not in ports.names
    assert "flush" not in ports.names


def test_flush_clears_fifo():
    config = {"width": 8, "depth": 4, "fall_through": True, "flush": True}
    actions = [
        {"set": {"wr_en": 1, "wdata": 0x11}, "edge": True},
        {
            "set": {"wr_en": 0, "flush": 1},
            "edge": True,
            "sample": ["empty"],
        },
        {"set": {"flush": 0}, "edge": True},
    ]
    assert _run(config, actions) == [(1,)]


def test_registered_outputs_breaks_path():
    config = {
        "width": 8,
        "depth": 2,
        "interface": "stream",
        "fall_through": True,
        "registered_outputs": True,
    }
    actions = [
        {"set": {"valid_in": 1, "data_in": 0x11, "ready_out": 0}, "edge": True},
        {
            "set": {"valid_in": 0},
            "edge": True,
            "sample": ["valid_out", "data_out"],
        },
    ]
    assert _run(config, actions) == [(1, 0x11)]


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        Fifo(width=8, depth=0)
    with pytest.raises(HdlConfigError):
        Fifo(width=8, depth=4, interface="sideways")


def test_configuration_matrix():
    for component in (
        Fifo(width=8, depth=2),
        Fifo(
            width=8,
            depth=2,
            interface="stream",
            fall_through=True,
            registered_outputs=True,
            count=True,
            almost_full=1,
            almost_empty=1,
            flush=True,
        ),
        Fifo(width=8, depth=4, interface="stream", fall_through=False),
    ):
        assert component.hdl(component.ports()) is not None
