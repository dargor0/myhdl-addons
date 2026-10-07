"""Verilog cosimulation smoke test for ``SyncRom`` (Option A)."""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.components import SyncRom

_INIT = [0x10, 0x20, 0x30, 0x40]


@block
def _tb(make_device, config, actions, results):
    comp = SyncRom(**config)
    ports = comp.ports()
    dut = make_device(comp, ports)
    # `clk`/`reset` only exist when a read/output stage exists (IC-FR-140)
    clk = ports["clk"] if "clk" in ports else Signal(bool(0))
    reset = ports["reset"] if "reset" in ports else Signal(bool(0))

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        reset.next = 0
        yield clk.posedge
        reset.next = 1
        for action in actions:
            for name, value in action.get("set", {}).items():
                getattr(ports, name).next = value
            if action.get("edge"):
                yield clk.posedge
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
        {"width": 8, "depth": 4, "init": _INIT},
        [{"set": {"raddr0": 2}, "edge": True, "sample": ["rdata0"]}],
    ),
    (
        {"width": 8, "depth": 4, "init": _INIT, "read_latency": 0},
        [{"set": {"raddr0": 3}, "sample": ["rdata0"]}],
    ),
    (
        {
            "width": 8,
            "depth": 4,
            "init": _INIT,
            "read_latency": 1,
            "output_register": True,
        },
        [
            {"set": {"raddr0": 1}, "edge": True, "sample": ["rdata0"]},
            {"edge": True, "sample": ["rdata0"]},
        ],
    ),
    (
        {"width": 8, "depth": 4, "init": _INIT, "read_ports": 2},
        [
            {
                "set": {"raddr0": 0, "raddr1": 3},
                "edge": True,
                "sample": ["rdata0", "rdata1"],
            }
        ],
    ),
]


@pytest.mark.parametrize("config,actions", _CASES)
def test_syncrom_cosim_matches_python(config, actions, hdl_cosim):
    python = _run(config, actions, _python_device)
    cosim = _run(config, actions, _cosim_device(hdl_cosim, "syncrom_cosim"))
    assert cosim == python
