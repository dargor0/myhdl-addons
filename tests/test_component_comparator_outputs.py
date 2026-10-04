"""Comparator flag semantics (``IC-FR-050..055``)."""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import AVAIL_OUTPUTS, Comparator


@block
def _python_device(comparator, ports):
    return comparator.hdl(ports)


@block
def _cmp_tb(make_device, results, width, a, b, signed):
    comparator = Comparator(width=width, outputs=AVAIL_OUTPUTS, signed=signed)
    ports = comparator.ports()
    dut = make_device(comparator, ports)

    @instance
    def stim():
        # Kick the converted logic with a known-different state first (cosim
        # does not re-evaluate when no input changes).
        ports.a.next = 0
        ports.b.next = (1 << width) - 1
        yield delay(1)
        ports.a.next = a
        ports.b.next = b
        yield delay(1)
        results.append({name: int(ports[name]) for name in AVAIL_OUTPUTS})
        raise StopSimulation

    return dut, stim


def _flags(width, a, b, signed=True, make_device=_python_device):
    results = []
    _cmp_tb(make_device, results, width, a, b, signed).run_sim()
    return results[0]


def _signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def _expected(a, b, width, signed):
    ltu = int(a < b)
    gtu = int(a > b)
    if signed:
        lt = int(_signed(a, width) < _signed(b, width))
        gt = int(_signed(a, width) > _signed(b, width))
        ge = int(_signed(a, width) >= _signed(b, width))
        le = int(_signed(a, width) <= _signed(b, width))
    else:
        lt, gt = ltu, gtu
        ge, le = int(a >= b), int(a <= b)
    return {
        "eq": int(a == b),
        "ne": int(a != b),
        "lt": lt,
        "ltu": ltu,
        "gt": gt,
        "gtu": gtu,
        "ge": ge,
        "le": le,
    }


_BOUNDARIES = (0x00, 0x01, 0x7F, 0x80, 0xFF)


@pytest.mark.parametrize("signed", [True, False])
@pytest.mark.parametrize("a", _BOUNDARIES)
@pytest.mark.parametrize("b", _BOUNDARIES)
def test_flag_matrix(a, b, signed):
    assert _flags(8, a, b, signed) == _expected(a, b, 8, signed)


def test_unsigned_greater():
    assert _flags(8, 5, 3) == _expected(5, 3, 8, True)


def test_equality():
    out = _flags(8, 42, 42)
    assert out["eq"] == 1 and out["ne"] == 0
    assert out["ge"] == 1 and out["le"] == 1


def test_signed_negative_less_than_positive():
    out = _flags(8, 0xFB, 0x03, signed=True)  # -5 < 3
    assert out["lt"] == 1 and out["gt"] == 0
    assert out["ltu"] == 0 and out["gtu"] == 1
    assert out["ge"] == 0 and out["le"] == 1


def test_unsigned_treats_as_large():
    out = _flags(8, 0xFB, 0x03, signed=False)
    assert out["lt"] == 0 and out["gt"] == 1


def test_signed_min_max():
    # 0x80 is the signed minimum, 0x7F the signed maximum.
    assert _flags(8, 0x80, 0x7F, signed=True)["lt"] == 1
    assert _flags(8, 0x7F, 0x80, signed=True)["gt"] == 1


def test_output_subset_removes_ports():
    out = _flags(8, 5, 3, signed=True)
    assert set(out) == set(AVAIL_OUTPUTS)
    comp = Comparator(width=8, outputs=("eq", "ltu"))
    names = comp.ports().names
    assert "eq" in names and "ltu" in names
    assert "gt" not in names and "ne" not in names
