"""Binary-to-one-hot decoder semantics (``IC-FR-070..074``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Decoder


@block
def _python_device(decoder, ports):
    return decoder.hdl(ports)


@block
def _dec_tb(make_device, results, n, sel, en=None, registered=0):
    decoder = Decoder(n=n, en=(en is not None), registered=registered)
    ports = decoder.ports()
    dut = make_device(decoder, ports)
    clk = ports.signals.get("clk")
    reset = ports.signals.get("reset")
    en_sig = ports.signals.get("en")
    sentinel = (sel + 1) % (1 << decoder.sel_bits)
    if registered:

        @always(delay(5))
        def clkgen():
            clk.next = not clk

    @instance
    def stim():
        if registered:
            reset.next = 0
            yield clk.posedge
            reset.next = 1
        # Kick the converted logic with a known-different state first.
        ports.sel.next = sentinel
        if en_sig is not None:
            en_sig.next = 0
        yield delay(1)
        ports.sel.next = sel
        if en_sig is not None:
            en_sig.next = en
        if registered:
            yield clk.posedge
        yield delay(1)
        results.append(int(ports.onehot))
        raise StopSimulation

    return (clkgen, dut, stim) if registered else (dut, stim)


def _run(sel, n=4, en=None, registered=0, make_device=_python_device):
    results = []
    _dec_tb(make_device, results, n, sel, en, registered).run_sim()
    return results[0]


def test_decodes_each_input():
    assert _run(0) == 0b0001
    assert _run(1) == 0b0010
    assert _run(2) == 0b0100
    assert _run(3) == 0b1000


def test_out_of_range_is_zero():
    assert _run(3, n=3) == 0


def test_enable_gates():
    assert _run(1, en=0) == 0
    assert _run(1, en=1) == 0b0010


def test_sel_width():
    assert Decoder(n=1).sel_bits == 1
    assert Decoder(n=5).sel_bits == 3


def test_registered_decoder():
    results = []
    _dec_tb(_python_device, results, 4, 2, registered=1).run_sim()
    assert results == [0b0100]
