"""ALU operation semantics (``IC-FR-010..016``)."""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import Alu


@block
def _alu_comb(
    results,
    width,
    a,
    b,
    opstr,
    ops=None,
    flags=("zero", "lt", "ltu", "carry"),
):
    alu = Alu(width=width, ops=ops, flags=flags)
    ports = alu.ports()
    op = alu.get_op_intmap().get(opstr, 0)
    dut = alu.hdl(ports)

    @instance
    def stim():
        ports.a.next = a
        ports.b.next = b
        ports.op.next = op
        yield delay(1)
        results.append((int(ports.y), {name: int(ports[name]) for name in flags}))
        raise StopSimulation

    return dut, stim


def _run(width, a, b, op, **kwargs):
    results = []
    #_alu_comb(results, width, a, b, op, **kwargs).run_sim()
    blocksim = _alu_comb(results, width, a, b, op, **kwargs)
    blocksim.run_sim()
    return results[0]


@pytest.mark.parametrize(
    ("w", "a", "b", "op", "expect"),
    [
        (8, 0x05, 0x03, "ADD", 0x08),
        (8, 0x05, 0x03, "SUB", 0x02),
        (8, 0x05, 0x03, "AND", 0x01),
        (8, 0x05, 0x03, "OR", 0x07),
        (8, 0x05, 0x03, "XOR", 0x06),
        (8, 0x05, 0x03, "SLT", 0x00),
        (8, 0x05, 0x03, "SLTU", 0x00),
        (8, 0x05, 0x03, "PASS_A", 0x05),
        (8, 0x05, 0x03, "PASS_B", 0x03),
    ],
)
def test_all_default_ops(w, a, b, op, expect):
    y, _ = _run(w, a, b, op)
    assert y == expect


def test_signed_vs_unsigned_compare():
    y, flags = _run(8, 0xFB, 0x03, "SLT")  # -5 < 3
    assert y == 1
    assert flags["lt"] == 1
    assert flags["ltu"] == 0
    assert flags["zero"] == 0


def test_subtraction_wraps():
    y, _ = _run(8, 0xFB, 0x03, "SUB")
    assert y == 0xF8


def test_zero_flag():
    y, flags = _run(8, 0x2A, 0x2A, "XOR")
    assert y == 0
    assert flags["zero"] == 1


def test_carry_flag_on_overflow():
    y, flags = _run(8, 0xFF, 0x01, "ADD", flags=("zero", "carry"))
    assert y == 0
    assert flags["zero"] == 1
    assert flags["carry"] == 1


def test_disabled_op_is_removed():
    y, _ = _run(8, 0x05, 0x03, "SUB", ops=["ADD"])
    assert y == 0


def test_flag_subset_removes_port():
    alu = Alu(width=8, flags=["zero"])
    assert "lt" not in alu.ports().names
    assert "zero" in alu.ports().names
