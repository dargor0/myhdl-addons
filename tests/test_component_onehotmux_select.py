"""One-hot mux semantics (``IC-FR-065..069``)."""

from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import OneHotMux


@block
def _onehot_tb(results, width, n, values, sel, valid=False, strict=False):
    mux = OneHotMux(width=width, n=n, valid=valid, strict=strict)
    ports = mux.ports()
    dut = mux.hdl(ports)
    valid_sig = ports.signals.get("valid")

    @instance
    def stim():
        for i, value in enumerate(values):
            ports.inputs[i].next = value
        ports.sel.next = sel
        yield delay(1)
        results.append(
            (int(ports.y), int(valid_sig) if valid_sig is not None else None)
        )
        raise StopSimulation

    return dut, stim


def _run(sel, values, width=8, **kwargs):
    results = []
    _onehot_tb(results, width, len(values), values, sel, **kwargs).run_sim()
    return results[0]


def test_one_hot_select():
    values = (0x11, 0x22, 0x33)
    assert _run(0b001, values)[0] == 0x11
    assert _run(0b010, values)[0] == 0x22
    assert _run(0b100, values)[0] == 0x33


def test_all_zero_is_zero():
    assert _run(0b000, (0x11, 0x22, 0x33))[0] == 0
    assert _run(0b000, (0x11, 0x22, 0x33), valid=True) == (0, 0)


def test_multi_hot_or_width():
    assert _run(0b011, (0x01, 0x02, 0x00))[0] == 0x03
    assert _run(0b111, (0x01, 0x04, 0x10))[0] == 0x15


def test_valid_any_bit():
    assert _run(0b001, (0x11, 0x22, 0x33), valid=True) == (0x11, 1)
    assert _run(0b110, (0x11, 0x22, 0x33), valid=True) == (0x33, 1)


def test_strict_valid_requires_exactly_one():
    values = (0x11, 0x22, 0x33)
    assert _run(0b001, values, valid=True, strict=True) == (0x11, 1)
    assert _run(0b011, values, valid=True, strict=True) == (0x33, 0)
    assert _run(0b111, values, valid=True, strict=True) == (0x33, 0)
    assert _run(0b000, values, valid=True, strict=True) == (0, 0)


def test_boundary_values():
    assert _run(0b10, (0x00, 0xFF), width=8)[0] == 0xFF
    assert _run(0b01, (0x7F, 0x00))[0] == 0x7F
    assert _run(0b01, (0x80, 0x00))[0] == 0x80
