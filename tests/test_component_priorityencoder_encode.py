"""Priority-encoder semantics (``IC-FR-075..078``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import PriorityEncoder


@block
def _pe_tb(results, n, din, priority="low", en=None, registered=0):
    encoder = PriorityEncoder(
        n=n, priority=priority, en=(en is not None), registered=registered
    )
    ports = encoder.ports()
    dut = encoder.hdl(ports)
    clk = ports.signals.get("clk")
    reset = ports.signals.get("reset")
    en_sig = ports.signals.get("en")
    if registered:

        @always(delay(5))
        def clkgen():
            clk.next = not clk

    @instance
    def stim():
        ports.din.next = din
        if en_sig is not None:
            en_sig.next = en
        if registered:
            reset.next = 1
            yield clk.posedge
            reset.next = 0
            yield clk.posedge
        yield delay(1)
        results.append((int(ports.index), int(ports.valid)))
        raise StopSimulation

    return (clkgen, dut, stim) if registered else (dut, stim)


def _run(din, **kwargs):
    results = []
    _pe_tb(results, kwargs.pop("n", 4), din, **kwargs).run_sim()
    return results[0]


def test_low_priority():
    assert _run(0b0100) == (2, 1)
    assert _run(0b1010) == (1, 1)
    assert _run(0b1111) == (0, 1)


def test_high_priority():
    assert _run(0b1010, priority="high") == (3, 1)
    assert _run(0b0100, priority="high") == (2, 1)


def test_all_zero_valid_low():
    assert _run(0b0000) == (0, 0)


def test_enable_gates_valid():
    assert _run(0b0100, en=0) == (2, 0)
    assert _run(0b0100, en=1) == (2, 1)


def test_index_width():
    assert PriorityEncoder(n=1).index_bits == 1
    assert PriorityEncoder(n=5).index_bits == 3


def test_registered_encoder():
    results = []
    _pe_tb(results, 4, 0b1000, registered=1).run_sim()
    assert results == [(3, 1)]
