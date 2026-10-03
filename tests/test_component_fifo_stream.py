"""FIFO stream/skid interface (``IC-FR-113..114``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import STREAM, Fifo


@block
def _stream_tb(results, config, actions):
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
    _stream_tb(results, config, actions).run_sim()
    return results


def test_stream_handshake_under_backpressure():
    config = {
        "width": 8,
        "depth": 2,
        "interface": STREAM,
        "fall_through": True,
    }
    actions = [
        {
            "set": {"valid_in": 1, "data_in": 0x11, "ready_out": 0},
            "edge": True,
            "sample": ["ready_in", "valid_out", "data_out"],
        },
        {
            "set": {"valid_in": 1, "data_in": 0x22, "ready_out": 0},
            "edge": True,
            "sample": ["ready_in", "valid_out", "data_out"],
        },
        {
            "set": {"valid_in": 0, "ready_out": 1},
            "edge": True,
            "sample": ["valid_out", "data_out", "ready_in"],
        },
        {
            "set": {"valid_in": 0, "ready_out": 1},
            "edge": True,
            "sample": ["valid_out"],
        },
    ]
    assert _run(config, actions) == [
        (1, 1, 0x11),
        (0, 1, 0x11),
        (1, 0x22, 1),
        (0,),
    ]


def test_stream_ports_names():
    ports = Fifo(width=8, depth=2, interface=STREAM).ports()
    assert {
        "valid_in",
        "ready_in",
        "data_in",
        "valid_out",
        "ready_out",
        "data_out",
    }.issubset(ports.names)
    assert "full" not in ports.names


def test_skid_buffer_is_depth_two_stream():
    # A skid buffer is Fifo(depth=2, interface="stream"): it accepts and
    # forwards two beats under backpressure (checked in the handshake test).
    fifo = Fifo(width=8, depth=2, interface=STREAM)
    assert fifo.as_dict()["depth"] == 2 and fifo.stream
    info = fifo.as_dict()
    assert info["interface"] == STREAM
    assert "Fifo" in repr(fifo)
