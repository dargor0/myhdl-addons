"""Combinational multiplier semantics (``MD-FR-001..007``).

Behaviour-first: a Python reference is compared against the simulated
multiplier over signed/unsigned operands, boundary values, both ``impl``
styles and an explicit ``dsptype`` (decomposition).
"""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import Multiplier


def _product(a, b, width, signed):
    """Reference full ``2*width``-bit product (bit pattern)."""
    full = (1 << (2 * width)) - 1
    if signed:
        a = a - (1 << width) if a & (1 << (width - 1)) else a
        b = b - (1 << width) if b & (1 << (width - 1)) else b
        return (a * b) & full
    return (a * b) & full


@block
def _python_device(mul, ports):
    return mul.hdl(ports)


@block
def _mul_bench(make_device, results, width, a, b, signed, impl, dsptype):
    mul = Multiplier(width=width, signed=signed, impl=impl, dsptype=dsptype)
    ports = mul.ports()
    dut = make_device(mul, ports)

    @instance
    def stim():
        ports.a.next = a
        ports.b.next = b
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return dut, stim


def _run(make_device, width, a, b, signed=True, impl="dsp", dsptype=None):
    results = []
    _mul_bench(make_device, results, width, a, b, signed, impl, dsptype).run_sim()
    return results[0]


# width 8: two's-complement boundaries and near-boundaries
_B8 = (0x00, 0x01, 0x02, 0x7F, 0x80, 0xFE, 0xFF)
_PAIRS8 = [(a, b) for a in _B8 for b in _B8]

# width 18: the hard-multiplier native width
_B18 = (0x00000, 0x00001, (1 << 17) - 1, 1 << 17, (1 << 18) - 2, (1 << 18) - 1)
_PAIRS18 = [(a, b) for a in _B18 for b in _B18]


@pytest.mark.parametrize("impl", ["dsp", "luts"])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("a,b", _PAIRS8)
def test_multiplier_matrix(a, b, signed, impl):
    assert _run(_python_device, 8, a, b, signed, impl) == _product(a, b, 8, signed)


@pytest.mark.parametrize("impl", ["dsp", "luts"])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("a,b", _PAIRS18)
def test_multiplier_width18(a, b, signed, impl):
    assert _run(_python_device, 18, a, b, signed, impl) == _product(a, b, 18, signed)


@pytest.mark.parametrize("dsptype", ["9x9", "18x18", "25x18", "27x18"])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("a,b", _PAIRS18)
def test_multiplier_dsptype_decomposition(a, b, signed, dsptype):
    # width > chunk only for 9x9; the others are a single multiply
    got = _run(_python_device, 18, a, b, signed, "dsp", dsptype)
    assert got == _product(a, b, 18, signed)


def test_multiplier_identity_and_annihilation():
    assert _run(_python_device, 8, 0x5A, 0x01) == 0x5A  # x*1
    assert _run(_python_device, 8, 0x5A, 0x00) == 0x00  # x*0
    assert _run(_python_device, 8, 0xFF, 0xFF) == _product(0xFF, 0xFF, 8, True)


def test_multiplier_ports_and_widths():
    comp = Multiplier(width=8)
    ports = comp.ports()
    assert ports.names == ["a", "b", "y"]
    assert len(ports.a) == 8 and len(ports.b) == 8
    assert len(ports.y) == 16  # full product, no truncation parameter


def test_multiplier_registered_absent():
    # Multiplier is purely combinational: no clock/reset ports.
    names = Multiplier(width=8).ports().names
    assert "clk" not in names and "reset" not in names


def test_multiplier_full_width_product():
    # the high half of the product must be preserved (no truncation)
    assert _run(_python_device, 8, 0xFF, 0xFF, False) == 0xFE01
    assert _run(_python_device, 4, 0xF, 0xF, False) == 0xE1


@pytest.mark.parametrize("impl", ["dsp", "luts"])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("width", [1, 2, 3])
def test_multiplier_exhaustive_small(width, signed, impl):
    # every operand pair of the smallest widths (catches sign/zero edge glue)
    for a in range(1 << width):
        for b in range(1 << width):
            assert _run(_python_device, width, a, b, signed, impl) == _product(
                a, b, width, signed
            )


@pytest.mark.parametrize("impl", ["dsp", "luts"])
@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("width", [9, 17, 18])
def test_multiplier_width_boundaries(width, signed, impl):
    values = (0, 1, 2, (1 << (width - 1)) - 1, 1 << (width - 1), (1 << width) - 1)
    for a in values:
        for b in values:
            assert _run(_python_device, width, a, b, signed, impl) == _product(
                a, b, width, signed
            )


@pytest.mark.parametrize(
    "width,dsptype", [(10, "9x9"), (13, "9x9"), (20, "18x18"), (25, "18x18")]
)
@pytest.mark.parametrize("signed", [True, False])
def test_multiplier_dsptype_ragged_chunks(width, dsptype, signed):
    # width not a multiple of the chunk -> a smaller top chunk
    values = (0, 1, (1 << (width - 1)) - 1, 1 << (width - 1), (1 << width) - 1)
    for a in values:
        for b in values:
            assert _run(
                _python_device, width, a, b, signed, "dsp", dsptype
            ) == _product(a, b, width, signed)


@pytest.mark.parametrize(
    "width,dsptype", [(8, "9x9"), (9, "9x9"), (18, "18x18"), (18, "25x18")]
)
def test_multiplier_dsptype_when_width_fits(width, dsptype):
    # width <= chunk -> a single multiply, still correct (both signs)
    full = (1 << width) - 1
    for a, b in ((0, 0), (full, full), (1 << (width - 1), 1)):
        assert _run(_python_device, width, a, b, True, "dsp", dsptype) == _product(
            a, b, width, True
        )
        assert _run(_python_device, width, a, b, False, "dsp", dsptype) == _product(
            a, b, width, False
        )


def test_multiplier_dsptype_ignored_for_luts():
    # impl="luts" ignores dsptype: same result with and without it
    for a, b in ((0xA5, 0x5A), (0xFF, 0xFF), (0x80, 0x80)):
        plain = _run(_python_device, 8, a, b, True, "luts", None)
        with_dsp = _run(_python_device, 8, a, b, True, "luts", "9x9")
        assert plain == with_dsp == _product(a, b, 8, True)
