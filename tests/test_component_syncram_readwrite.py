"""SyncRam read/write, latency and write modes (``IC-FR-100..107``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import WRITE_FIRST, SyncRam


@block
def _ram_tb(results, config, actions):
    ram = SyncRam(**config)
    ports = ram.ports()
    dut = ram.hdl(ports)

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
    _ram_tb(results, config, actions).run_sim()
    return results


def test_registered_read():
    config = {"width": 8, "depth": 4, "read_latency": 1}
    actions = [
        {"set": {"we0": 1, "waddr0": 1, "wdata0": 0xAB}, "edge": True},
        {"set": {"we0": 0, "raddr0": 1}, "edge": True, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0xAB,)]


def test_combinational_read():
    config = {"width": 8, "depth": 4, "read_latency": 0}
    actions = [
        {"set": {"we0": 1, "waddr0": 1, "wdata0": 0xCD}, "edge": True},
        {"set": {"we0": 0, "raddr0": 1}, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0xCD,)]


def test_write_first_bypass():
    config = {"width": 8, "depth": 4, "read_latency": 1, "write_mode": WRITE_FIRST}
    actions = [
        {
            "set": {"raddr0": 2, "we0": 1, "waddr0": 2, "wdata0": 0x55},
            "edge": True,
            "sample": ["rdata0"],
        }
    ]
    assert _run(config, actions) == [(0x55,)]


def test_output_register_adds_latency():
    config = {"width": 8, "depth": 4, "read_latency": 1, "output_register": True}
    actions = [
        {"set": {"we0": 1, "waddr0": 1, "wdata0": 0xAB}, "edge": True},
        {"set": {"we0": 0, "raddr0": 1}, "edge": True, "sample": ["rdata0"]},
        {"edge": True, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0,), (0xAB,)]


def test_byte_write_strobes():
    config = {"width": 16, "depth": 4, "read_latency": 1, "byte_write": 2}
    actions = [
        {
            "set": {"we0": 1, "waddr0": 0, "wdata0": 0x1234, "wstrb0": 0b10},
            "edge": True,
        },
        {"set": {"we0": 0, "raddr0": 0}, "edge": True, "sample": ["rdata0"]},
    ]
    assert _run(config, actions) == [(0x1200,)]


def test_init_image_survives_reset():
    config = {"width": 8, "depth": 4, "read_latency": 1, "init": [1, 2, 3, 4]}
    actions = [{"set": {"raddr0": 3}, "edge": True, "sample": ["rdata0"]}]
    assert _run(config, actions) == [(4,)]


def test_out_of_range_read_is_zero():
    config = {"width": 8, "depth": 3, "read_latency": 1}
    actions = [{"set": {"raddr0": 3}, "edge": True, "sample": ["rdata0"]}]
    assert _run(config, actions) == [(0,)]


def test_as_dict():
    ram = SyncRam(width=16, depth=8, read_latency=0, output_register=True)
    info = ram.as_dict()
    assert info["read_latency"] == 0
    assert info["output_register"] is True
    assert "SyncRam" in repr(ram)
