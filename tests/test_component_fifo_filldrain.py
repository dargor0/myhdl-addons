"""FIFO native fill/drain, flags and overflow (``IC-FR-110..112``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Fifo


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
    _fifo_tb(results, config, actions).run_sim()
    return results


def test_fall_through_fill_drain_and_overflow():
    config = {"width": 8, "depth": 2, "fall_through": True}
    actions = [
        {"set": {"wr_en": 1, "wdata": 0x11}, "edge": True},
        {
            "set": {"wr_en": 1, "wdata": 0x22},
            "edge": True,
            "sample": ["rdata", "full", "empty"],
        },
        {"set": {"wr_en": 1, "wdata": 0x99}, "edge": True},
        {
            "set": {"wr_en": 0, "rd_en": 1},
            "edge": True,
            "sample": ["rdata", "full", "empty"],
        },
        {"set": {"rd_en": 1}, "edge": True, "sample": ["rdata", "empty"]},
        {"set": {"rd_en": 1}, "edge": True, "sample": ["empty"]},
    ]
    assert _run(config, actions) == [
        (0x11, 1, 0),
        (0x22, 0, 0),
        (0x22, 1),
        (1,),
    ]


def test_registered_read_pops_with_one_cycle_latency():
    config = {"width": 8, "depth": 2, "fall_through": False}
    actions = [
        {"set": {"wr_en": 1, "wdata": 0xAB}, "edge": True},
        {"set": {"wr_en": 0, "rd_en": 1}, "edge": True, "sample": ["rdata"]},
        {"set": {"rd_en": 0}, "edge": True, "sample": ["rdata", "empty"]},
    ]
    assert _run(config, actions) == [(0xAB,), (0xAB, 1)]


def test_depth_one_fifo():
    config = {"width": 8, "depth": 1, "fall_through": True}
    actions = [
        {"set": {"wr_en": 1, "wdata": 0x5A}, "edge": True, "sample": ["full"]},
        {"set": {"wr_en": 0, "rd_en": 1}, "edge": True, "sample": ["empty"]},
    ]
    assert _run(config, actions) == [(1,), (1,)]
