"""Verilog cosimulation smoke test for ``Fifo`` (Option A).

The same clocked bench drives either the Python block or the converted Verilog
RTL; both must produce identical samples.
"""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Fifo


@block
def _tb(make_device, config, actions, results):
    comp = Fifo(**config)
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        # force a reset transition (power-on is already 0): this also defines
        # the converted combinational reset path before the first edge
        ports.reset.next = 1
        yield delay(1)
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
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


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name)

    return _make


def _run(config, actions, make_device):
    results = []
    _tb(make_device, config, actions, results).run_sim()
    return results


_CASES = [
    (
        {"width": 8, "depth": 2, "fall_through": True},
        [
            {"set": {"wr_en": 1, "wdata": 0x11}, "edge": True},
            {
                "set": {"wr_en": 1, "wdata": 0x22},
                "edge": True,
                "sample": ["rdata", "full", "empty"],
            },
            {"set": {"wr_en": 0, "rd_en": 1}, "edge": True, "sample": ["rdata"]},
            {"set": {"rd_en": 1}, "edge": True, "sample": ["rdata", "empty"]},
        ],
    ),
    (
        {"width": 8, "depth": 2, "fall_through": False},
        [
            {"set": {"wr_en": 1, "wdata": 0xAB}, "edge": True},
            {"set": {"wr_en": 0, "rd_en": 1}, "edge": True, "sample": ["rdata"]},
            {"set": {"rd_en": 0}, "edge": True, "sample": ["rdata", "empty"]},
        ],
    ),
    (
        {"width": 8, "depth": 4, "count": True, "flush": True, "almost_full": 3},
        [
            {"set": {"wr_en": 1, "wdata": 0x33}, "edge": True},
            {
                "set": {"wr_en": 0},
                "edge": True,
                "sample": ["count", "full", "empty", "almost_full"],
            },
            {"set": {"flush": 1}, "edge": True, "sample": ["count", "empty"]},
        ],
    ),
]


@pytest.mark.parametrize("config,actions", _CASES)
def test_fifo_cosim_matches_python(config, actions, hdl_cosim):
    python = _run(config, actions, _python_device)
    cosim = _run(config, actions, _cosim_device(hdl_cosim, "fifo_cosim"))
    assert cosim == python
