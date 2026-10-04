"""AddressDecoder window semantics (``IC-FR-089..095``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import AddressDecoder

_WINDOWS = ((0x00, 0x10), (0x20, 0x10), (0x40, 0x20))


@block
def _python_device(dec, ports):
    return dec.hdl(ports)


@block
def _ad_tb(make_device, results, config, adr, en=None, sample_valid=False):
    config = {**config, "valid": True}
    dec = AddressDecoder(**config)
    ports = dec.ports()
    dut = make_device(dec, ports)
    clk = ports.signals.get("clk")
    reset = ports.signals.get("reset")
    en_sig = ports.signals.get("en")
    registered = config.get("registered", 0)
    sentinel = (1 << config["adr_width"]) - 1
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
        # Kick the converted logic with a known-different state first (cosim
        # does not re-evaluate when no input changes).
        ports.adr.next = sentinel
        if en_sig is not None:
            en_sig.next = 0
        yield delay(1)
        ports.adr.next = adr
        if en_sig is not None:
            en_sig.next = en
        if registered:
            yield clk.posedge
        yield delay(1)
        sampled = [int(ports[f"sel{i}"]) for i in range(len(config["windows"]))]
        if sample_valid:
            sampled.append(int(ports.valid))
        results.append(tuple(sampled))
        raise StopSimulation

    return (clkgen, dut, stim) if registered else (dut, stim)


def _run(config, adr, en=None, sample_valid=False, *, make_device=_python_device):
    results = []
    _ad_tb(make_device, results, config, adr, en, sample_valid).run_sim()
    return results[0]


def test_address_matches_each_window():
    config = {"adr_width": 8, "windows": _WINDOWS}
    assert _run(config, 0x00) == (1, 0, 0)
    assert _run(config, 0x0F) == (1, 0, 0)
    assert _run(config, 0x20) == (0, 1, 0)
    assert _run(config, 0x2F) == (0, 1, 0)
    assert _run(config, 0x40) == (0, 0, 1)
    assert _run(config, 0x5F) == (0, 0, 1)


def test_window_boundaries():
    config = {"adr_width": 8, "windows": ((0x20, 0x10),)}
    assert _run(config, 0x1F) == (0,)  # base - 1
    assert _run(config, 0x20) == (1,)  # base
    assert _run(config, 0x2F) == (1,)  # base + size - 1
    assert _run(config, 0x30) == (0,)  # base + size


def test_out_of_range_is_all_zero():
    config = {"adr_width": 8, "windows": _WINDOWS}
    assert _run(config, 0x10) == (0, 0, 0)
    assert _run(config, 0xFF) == (0, 0, 0)


def test_enable_gates_selects():
    config = {"adr_width": 8, "windows": _WINDOWS, "en": True}
    assert _run(config, 0x20, en=0) == (0, 0, 0)
    assert _run(config, 0x20, en=1) == (0, 1, 0)


def test_valid_flag():
    config = {"adr_width": 8, "windows": _WINDOWS, "valid": True}
    assert _run(config, 0x20, sample_valid=True) == (0, 1, 0, 1)
    assert _run(config, 0x10, sample_valid=True) == (0, 0, 0, 0)


def test_valid_respects_enable():
    config = {"adr_width": 8, "windows": _WINDOWS, "en": True, "valid": True}
    assert _run(config, 0x40, en=0, sample_valid=True) == (0, 0, 0, 0)
    assert _run(config, 0x40, en=1, sample_valid=True) == (0, 0, 1, 1)


def test_registered_output_latency():
    config = {"adr_width": 8, "windows": _WINDOWS, "registered": 1, "valid": True}
    assert _run(config, 0x20, sample_valid=True) == (0, 1, 0, 1)
