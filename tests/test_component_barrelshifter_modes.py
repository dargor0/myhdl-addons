"""Barrel shifter modes and shift-amount behaviour (``IC-FR-030..039``)."""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import ROL, ROR, SLL, SRA, SRL, BarrelShifter


@block
def _shift_tb(
    results,
    width,
    data,
    shamt,
    mode,
    modes=None,
    structure="logarithmic",
    shamt_mode="modulo",
    shamt_bits=None,
    shamt_const=None,
):
    shifter = BarrelShifter(
        width=width,
        modes=modes,
        structure=structure,
        shamt_mode=shamt_mode,
        shamt_bits=shamt_bits,
        shamt_const=shamt_const,
    )
    ports = shifter.ports()
    dut = shifter.hdl(ports)
    shamt_sig = ports.signals.get("shamt")

    @instance
    def stim():
        ports.data.next = data
        ports.mode.next = mode
        if shamt_sig is not None:
            shamt_sig.next = shamt
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return dut, stim


def _run(width, data, shamt, mode, **kwargs):
    results = []
    _shift_tb(results, width, data, shamt, mode, **kwargs).run_sim()
    return results[0]


@pytest.mark.parametrize(
    ("mode", "data", "shamt", "expect"),
    [
        (SLL, 0x01, 3, 0x08),
        (SRL, 0x80, 3, 0x10),
        (SRA, 0x80, 3, 0xF0),
        (ROL, 0x81, 1, 0x03),
        (ROR, 0x81, 1, 0xC0),
    ],
)
def test_all_modes(mode, data, shamt, expect):
    assert _run(8, data, shamt, mode) == expect


def test_modulo_wraps_amount():
    assert _run(8, 0x01, 10, SLL, shamt_bits=5) == 0x04


def test_zero_mode_out_of_range_is_zero():
    assert _run(8, 0x01, 10, SLL, shamt_mode="zero", shamt_bits=5) == 0
    assert _run(8, 0xFF, 8, SRL, shamt_mode="zero", shamt_bits=5) == 0


def test_saturate_mode():
    assert _run(8, 0x01, 10, SLL, shamt_mode="saturate") == 0
    assert _run(8, 0x80, 10, SRA, shamt_mode="saturate") == 0xFF
    assert _run(8, 0x80, 10, SRL, shamt_mode="saturate") == 0
    assert _run(8, 0x5A, 10, ROL, shamt_mode="saturate") == 0x5A


def test_structures_agree():
    args = (8, 0xA5, 3, ROR)
    results = [_run(*args, structure=s) for s in ("logarithmic", "two_stage", "serial")]
    assert results[0] == results[1] == results[2]


def test_disabled_mode_is_zero():
    assert _run(8, 0x01, 1, SLL, modes=["SRL"]) == 0


def test_shamt_const_omits_port():
    shifter = BarrelShifter(width=8, shamt_const=2, modes=["SLL"])
    ports = shifter.ports()
    assert "shamt" not in ports.names
    results = []
    _shift_tb(results, 8, 0x01, 0, SLL, shamt_const=2, modes=["SLL"]).run_sim()
    assert results[0] == 0x04


def _reference(mode, data, shamt, width, shamt_mode="modulo"):
    """Reference model matching ``IC-FR-032``/``IC-FR-033``."""
    full = (1 << width) - 1
    value = data & full
    if shamt_mode == "modulo":
        amount = shamt & (width - 1)
    elif shamt_mode == "zero":
        if shamt >= width:
            return 0
        amount = shamt
    else:  # saturate
        if shamt >= width:
            if mode == SRA:
                return full if (value >> (width - 1)) & 1 else 0
            if mode in (ROL, ROR):
                return value
            return 0
        amount = shamt
    if mode == SLL:
        return (value << amount) & full
    if mode == SRL:
        return (value >> amount) & full
    if mode == SRA:
        signed = value - (1 << width) if value & (1 << (width - 1)) else value
        return (signed >> amount) & full
    amount %= width
    if mode == ROL:
        if amount == 0:
            return value
        return ((value << amount) | (value >> (width - amount))) & full
    if amount == 0:
        return value
    return ((value >> amount) | (value << (width - amount))) & full


_CASES = [(0x00, 0), (0x01, 1), (0x80, 7), (0xA5, 4)]


@pytest.mark.parametrize("mode", [SLL, SRL, SRA, ROL, ROR])
@pytest.mark.parametrize("structure", ["logarithmic", "two_stage", "serial"])
@pytest.mark.parametrize(("data", "shamt"), _CASES)
def test_modes_structures_matrix(mode, structure, data, shamt):
    expect = _reference(mode, data, shamt, 8)
    assert _run(8, data, shamt, mode, structure=structure) == expect


@pytest.mark.parametrize("mode", [SLL, SRL, SRA, ROL, ROR])
@pytest.mark.parametrize("const", [0, 3, 7])
def test_shamt_const_all_modes(mode, const):
    expect = _reference(mode, 0xA5, const, 8)
    assert _run(8, 0xA5, 0, mode, shamt_const=const) == expect


@pytest.mark.parametrize("mode", [SLL, SRL, SRA, ROL, ROR])
@pytest.mark.parametrize("shamt_mode", ["zero", "saturate"])
def test_out_of_range_all_modes(mode, shamt_mode):
    expect = _reference(mode, 0x80, 10, 8, shamt_mode)
    assert _run(8, 0x80, 10, mode, shamt_mode=shamt_mode, shamt_bits=5) == expect


@pytest.mark.parametrize("mode", [SLL, SRL, SRA, ROL, ROR])
@pytest.mark.parametrize("shamt_mode", ["zero", "saturate"])
def test_const_out_of_range_all_modes(mode, shamt_mode):
    expect = _reference(mode, 0x80, 10, 8, shamt_mode)
    assert _run(8, 0x80, 0, mode, shamt_const=10, shamt_mode=shamt_mode) == expect


def test_saturate_sra_positive_sign_is_zero():
    assert _run(8, 0x40, 10, SRA, shamt_mode="saturate", shamt_bits=5) == 0
    assert _run(8, 0x40, 0, SRA, shamt_const=10, shamt_mode="saturate") == 0
