"""Verilog cosimulation smoke test for ``RegisterFile`` (Option A)."""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import NO_CHANGE, WRITE_FIRST, RegisterFile


@block
def _tb(make_device, config, actions, results):
    comp = RegisterFile(**config)
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
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
        {"width": 8, "depth": 4, "read_ports": 2, "write_ports": 1, "read_latency": 0},
        [
            {"set": {"we0": 1, "waddr0": 1, "wdata0": 0xAB}, "edge": True},
            {
                "set": {"we0": 0, "raddr0": 1, "raddr1": 1},
                "sample": ["rdata0", "rdata1"],
            },
        ],
    ),
    (
        {
            "width": 8,
            "depth": 4,
            "read_ports": 1,
            "write_ports": 1,
            "read_latency": 1,
            "write_mode": WRITE_FIRST,
        },
        [
            {
                "set": {"raddr0": 2, "we0": 1, "waddr0": 2, "wdata0": 0x55},
                "edge": True,
                "sample": ["rdata0"],
            }
        ],
    ),
    (
        {
            "width": 8,
            "depth": 4,
            "read_ports": 1,
            "write_ports": 1,
            "read_latency": 1,
            "write_mode": NO_CHANGE,
        },
        [
            {"set": {"we0": 1, "waddr0": 2, "wdata0": 0x11}, "edge": True},
            {"set": {"we0": 0, "raddr0": 2}, "edge": True, "sample": ["rdata0"]},
            {
                "set": {"we0": 1, "waddr0": 2, "wdata0": 0x22},
                "edge": True,
                "sample": ["rdata0"],
            },
        ],
    ),
    (
        {"width": 8, "depth": 4, "zero_reg_fix_value": 0, "read_latency": 0},
        [
            {"set": {"we0": 1, "waddr0": 0, "wdata0": 0xEE}, "edge": True},
            {"set": {"we0": 0, "raddr0": 0}, "sample": ["rdata0"]},
        ],
    ),
    (
        {"width": 16, "depth": 4, "byte_write": True, "read_latency": 0},
        [
            # define the word first (writable memory is undefined at time 0)
            {
                "set": {"we0": 1, "waddr0": 0, "wdata0": 0x0000, "wstrb0": 0b11},
                "edge": True,
            },
            {
                "set": {"we0": 1, "waddr0": 0, "wdata0": 0xABCD, "wstrb0": 0b01},
                "edge": True,
            },
            {"set": {"we0": 0, "raddr0": 0}, "sample": ["rdata0"]},
        ],
    ),
]


@pytest.mark.parametrize("config,actions", _CASES)
def test_registerfile_cosim_matches_python(config, actions, hdl_cosim):
    python = _run(config, actions, _python_device)
    cosim = _run(config, actions, _cosim_device(hdl_cosim, "regfile_cosim"))
    assert cosim == python
