"""Register-file reads/writes and write modes (``IC-FR-020..028``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import (
    NO_CHANGE,
    READ_FIRST,
    WRITE_FIRST,
    RegisterFile,
)


@block
def _rf_tb(results, config, actions):
    rf = RegisterFile(**config)
    ports = rf.ports()
    dut = rf.hdl(ports)

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


def _run(config, actions):
    results = []
    _rf_tb(results, config, actions).run_sim()
    return results


def test_async_reads_and_writes():
    config = {
        "width": 8,
        "depth": 4,
        "read_ports": 2,
        "write_ports": 1,
        "read_latency": 0,
    }
    actions = [
        {"set": {"we0": 1, "waddr0": 1, "wdata0": 0xAB}, "edge": True},
        {"set": {"we0": 0, "raddr0": 1, "raddr1": 1}, "sample": ["rdata0", "rdata1"]},
    ]
    assert _run(config, actions) == [(0xAB, 0xAB)]


def test_registered_read_write_first():
    config = {
        "width": 8,
        "depth": 4,
        "read_ports": 1,
        "write_ports": 1,
        "read_latency": 1,
        "write_mode": WRITE_FIRST,
    }
    actions = [
        {
            "set": {"raddr0": 2, "we0": 1, "waddr0": 2, "wdata0": 0x55},
            "edge": True,
            "sample": ["rdata0"],
        }
    ]
    assert _run(config, actions) == [(0x55,)]


def test_registered_read_read_first():
    config = {
        "width": 8,
        "depth": 4,
        "read_ports": 1,
        "write_ports": 1,
        "read_latency": 1,
        "write_mode": READ_FIRST,
    }
    actions = [
        {"set": {"we0": 1, "waddr0": 2, "wdata0": 0x11}, "edge": True},
        {"set": {"we0": 0, "raddr0": 2}, "edge": True, "sample": ["rdata0"]},
        {
            "set": {"we0": 1, "waddr0": 2, "wdata0": 0x22},
            "edge": True,
            "sample": ["rdata0"],
        },
    ]
    assert _run(config, actions) == [(0x11,), (0x11,)]


def test_registered_read_no_change():
    config = {
        "width": 8,
        "depth": 4,
        "read_ports": 1,
        "write_ports": 1,
        "read_latency": 1,
        "write_mode": NO_CHANGE,
    }
    actions = [
        {"set": {"we0": 1, "waddr0": 2, "wdata0": 0x11}, "edge": True},
        {"set": {"we0": 0, "raddr0": 2}, "edge": True, "sample": ["rdata0"]},
        {
            "set": {"we0": 1, "waddr0": 2, "wdata0": 0x22},
            "edge": True,
            "sample": ["rdata0"],
        },
    ]
    assert _run(config, actions) == [(0x11,), (0x11,)]


def test_zero_reg_fix_value_is_read_only():
    config = {"width": 8, "depth": 4, "zero_reg_fix_value": 0, "read_latency": 0}
    actions = [
        {"set": {"we0": 1, "waddr0": 0, "wdata0": 0xEE}, "edge": True},
        {"set": {"we0": 0, "raddr0": 0}, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0,)]


def test_byte_write_strobes():
    config = {
        "width": 16,
        "depth": 4,
        "byte_write": True,
        "read_latency": 0,
    }
    actions = [
        {
            "set": {"we0": 1, "waddr0": 0, "wdata0": 0xABCD, "wstrb0": 0b01},
            "edge": True,
        },
        {"set": {"we0": 0, "raddr0": 0}, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0x00CD,)]


def test_init_image_without_reset():
    config = {
        "width": 8,
        "depth": 4,
        "reset_enable": False,
        "init": [0x11, 0x22, 0x33, 0x44],
        "read_latency": 0,
    }
    actions = [{"set": {"raddr0": 2}, "sample": ["rdata0"]}]
    assert _run(config, actions) == [(0x33,)]


def test_single_port_configuration():
    config = {"width": 8, "depth": 4, "read_ports": 1, "write_ports": 1}
    actions = [
        {"set": {"we0": 1, "waddr0": 3, "wdata0": 0x7E}, "edge": True},
        {"set": {"we0": 0, "raddr0": 3}, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0x7E,)]
