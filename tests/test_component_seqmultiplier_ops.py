"""Sequential (shift-and-add) multiplier semantics (``MD-FR-020..025``).

A Python reference is compared against the simulated block over signed/unsigned
operands, radix 2 and 4, boundary values, and the start/busy/done protocol.
"""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.components import SequentialMultiplier


def _product(a, b, width, signed):
    full = (1 << (2 * width)) - 1
    if signed:
        a = a - (1 << width) if a & (1 << (width - 1)) else a
        b = b - (1 << width) if b & (1 << (width - 1)) else b
    return (a * b) & full


def _iterations(width, radix):
    shift = 1 if radix == 2 else 2
    return (width + shift - 1) // shift


@block
def _python_device(mul, ports):
    return mul.hdl(ports)


@block
def _seq_bench(make_device, results, width, a, b, signed, radix, en):
    mul = SequentialMultiplier(width=width, signed=signed, radix=radix, en=en)
    ports = mul.ports()
    dut = make_device(mul, ports)
    # Bind the enable at elaboration: when disabled there is no `en` port, and a
    # static `ports.en` reference inside the generator would fail MyHDL's
    # reference resolver (the dummy drive is harmless).
    en_drive = ports.en if en else Signal(bool(0))

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0  # active-low: asserted
        yield ports.clk.posedge
        ports.reset.next = 1  # release
        yield ports.clk.posedge

        ports.a.next = a
        ports.b.next = b
        en_drive.next = 1
        ports.start.next = 1
        yield ports.clk.posedge
        ports.start.next = 0
        cycles = 0
        while not ports.done:
            yield ports.clk.posedge
            cycles += 1
            # Let the FSM's edge update settle before sampling `done`, otherwise
            # this process can observe the pre-edge value and count one too many.
            yield delay(1)
        results.append((int(ports.y), cycles))
        raise StopSimulation

    return clkgen, dut, stim


def _run(make_device, width, a, b, signed=True, radix=2, en=False):
    results = []
    _seq_bench(make_device, results, width, a, b, signed, radix, en).run_sim()
    return results[0]


_B8 = (0x00, 0x01, 0x02, 0x7F, 0x80, 0xFE, 0xFF)
_PAIRS8 = [(a, b) for a in _B8 for b in _B8]


@pytest.mark.parametrize("radix", [2, 4])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("a,b", _PAIRS8)
def test_seq_matrix(a, b, signed, radix):
    expected = (_product(a, b, 8, signed), _iterations(8, radix))
    assert _run(_python_device, 8, a, b, signed, radix) == expected


@pytest.mark.parametrize("radix", [2, 4])
@pytest.mark.parametrize("signed", [True, False])
def test_seq_width18(signed, radix):
    bounds = (0x00000, 0x00001, 1 << 17, (1 << 18) - 1)
    for a in bounds:
        for b in bounds:
            expected = (_product(a, b, 18, signed), _iterations(18, radix))
            assert _run(_python_device, 18, a, b, signed, radix) == expected


@block
def _seq_multi_bench(results, width, jobs):
    mul = SequentialMultiplier(width=width)
    ports = mul.ports()
    dut = mul.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        yield ports.clk.posedge
        for a, b in jobs:
            ports.a.next = a
            ports.b.next = b
            ports.start.next = 1
            yield ports.clk.posedge
            ports.start.next = 0
            while not ports.done:
                yield ports.clk.posedge
            yield delay(1)
            results.append(int(ports.y))
            yield ports.clk.posedge  # one idle cycle
        raise StopSimulation

    return clkgen, dut, stim


def test_seq_back_to_back_transactions():
    jobs = [(3, 4), (0x80, 0x02), (0xFF, 0xFF)]
    results = []
    _seq_multi_bench(results, 8, jobs).run_sim()
    assert results == [_product(a, b, 8, True) for a, b in jobs]


@block
def _seq_stall_bench(results):
    mul = SequentialMultiplier(width=8, en=True)
    ports = mul.ports()
    dut = mul.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        yield ports.clk.posedge

        ports.a.next = 0x80
        ports.b.next = 0x80
        ports.en.next = 0  # stalled from the start
        ports.start.next = 1
        yield ports.clk.posedge
        ports.start.next = 0
        for _ in range(4):  # hold the stall
            yield ports.clk.posedge
        results.append(int(ports.done))
        ports.en.next = 1  # release
        while not ports.done:
            yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return clkgen, dut, stim


def test_seq_en_stalls_iteration():
    results = []
    _seq_stall_bench(results).run_sim()
    assert results == [0, _product(0x80, 0x80, 8, True)]


@block
def _seq_reset_bench(results):
    mul = SequentialMultiplier(width=8, reset_value=0x1234)
    ports = mul.ports()
    dut = mul.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 1  # released (active-low)
        yield ports.clk.posedge
        ports.a.next = 0x40
        ports.b.next = 0x04
        ports.start.next = 1
        yield ports.clk.posedge
        ports.start.next = 0
        yield ports.clk.posedge  # mid-flight
        ports.reset.next = 0  # assert reset
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.busy), int(ports.done)))
        raise StopSimulation

    return clkgen, dut, stim


def test_seq_reset_mid_flight():
    results = []
    _seq_reset_bench(results).run_sim()
    assert results == [(0x1234, 0, 0)]


def test_seq_ports_and_widths():
    comp = SequentialMultiplier(width=8)
    ports = comp.ports()
    assert {"clk", "reset", "start", "a", "b", "y", "busy", "done"}.issubset(
        ports.names
    )
    assert "en" not in ports.names
    assert len(ports.y) == 16
    assert SequentialMultiplier(width=8, en=True).ports().names.count("en") == 1


def test_seq_iterations_property():
    assert SequentialMultiplier(width=18, radix=2).iterations == 18
    assert SequentialMultiplier(width=18, radix=4).iterations == 9
    assert SequentialMultiplier(width=7, radix=4).iterations == 4


@pytest.mark.parametrize("width,radix", [(1, 2), (2, 2), (1, 4), (2, 4), (3, 4)])
@pytest.mark.parametrize("signed", [True, False])
def test_seq_exhaustive_small(width, signed, radix):
    for a in range(1 << width):
        for b in range(1 << width):
            expected = (_product(a, b, width, signed), _iterations(width, radix))
            assert _run(_python_device, width, a, b, signed, radix) == expected


@pytest.mark.parametrize("width,radix", [(5, 4), (7, 4), (17, 4), (19, 2)])
@pytest.mark.parametrize("signed", [True, False])
def test_seq_odd_widths(width, signed, radix):
    # radix-4 with an odd/ragged width still consumes every multiplier bit
    values = (0, 1, (1 << (width - 1)) - 1, 1 << (width - 1), (1 << width) - 1)
    for a in values:
        for b in values:
            expected = (_product(a, b, width, signed), _iterations(width, radix))
            assert _run(_python_device, width, a, b, signed, radix) == expected
