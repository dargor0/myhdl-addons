"""SyncRom read behaviour (``IC-FR-140..144``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import SyncRom


@block
def _rom_tb(results, config, actions):
    rom = SyncRom(**config)
    ports = rom.ports()
    dut = rom.hdl(ports)

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
    _rom_tb(results, config, actions).run_sim()
    return results


def test_registered_read():
    config = {"width": 8, "depth": 4, "init": [0x10, 0x20, 0x30, 0x40]}
    actions = [{"set": {"raddr0": 2}, "edge": True, "sample": ["rdata0"]}]
    assert _run(config, actions) == [(0x30,)]


def test_combinational_read():
    config = {
        "width": 8,
        "depth": 4,
        "init": [0x10, 0x20, 0x30, 0x40],
        "read_latency": 0,
    }
    actions = [{"set": {"raddr0": 3}, "sample": ["rdata0"]}]
    assert _run(config, actions) == [(0x40,)]


def test_output_register_adds_latency():
    config = {
        "width": 8,
        "depth": 4,
        "init": [0x10, 0x20, 0x30, 0x40],
        "read_latency": 1,
        "output_register": True,
    }
    actions = [
        {"set": {"raddr0": 1}, "edge": True, "sample": ["rdata0"]},
        {"edge": True, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0,), (0x20,)]


def test_out_of_range_read_is_zero():
    config = {"width": 8, "depth": 3, "init": [1, 2, 3]}
    actions = [{"set": {"raddr0": 3}, "edge": True, "sample": ["rdata0"]}]
    assert _run(config, actions) == [(0,)]


def test_two_read_ports():
    config = {
        "width": 8,
        "depth": 4,
        "init": [0x10, 0x20, 0x30, 0x40],
        "read_ports": 2,
    }
    actions = [
        {
            "set": {"raddr0": 0, "raddr1": 3},
            "edge": True,
            "sample": ["rdata0", "rdata1"],
        }
    ]
    assert _run(config, actions) == [(0x10, 0x40)]


def test_as_dict():
    rom = SyncRom(width=8, depth=4, init=[1, 2, 3, 4])
    info = rom.as_dict()
    assert info["depth"] == 4
    assert info["init"] == (1, 2, 3, 4)
    assert "SyncRom" in repr(rom)
