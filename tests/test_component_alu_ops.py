"""ALU operation semantics (``IC-FR-010..016``).

Behaviour-first: a Python reference is compared against the simulated ALU over
every enabled op and a boundary/edge operand matrix (two's-complement signs,
carry/borrow, wraparound, zero, pass-through).
"""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import AVAIL_FLAGS, AVAIL_OPS, Alu


@block
def _alu_comb(results, width, a, b, opstr, ops=None, flags=AVAIL_FLAGS):
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
        results.append(
            {
                "y": int(ports.y),
                "zero": int(ports.zero),
                "lt": int(ports.lt),
                "ltu": int(ports.ltu),
                "carry": int(ports.carry),
            }
        )
        raise StopSimulation

    return dut, stim


def _run(width, a, b, opstr, **kwargs):
    results = []
    _alu_comb(results, width, a, b, opstr, **kwargs).run_sim()
    return results[0]


def _signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def _reference(op, a, b, width):
    full = (1 << width) - 1
    carry = 0
    if op == "ADD":
        total = a + b
        y = total & full
        carry = int(total > full)
    elif op == "SUB":
        y = (a - b) & full
        carry = int(b > a)
    elif op == "AND":
        y = a & b
    elif op == "OR":
        y = a | b
    elif op == "XOR":
        y = a ^ b
    elif op == "SLT":
        y = int(_signed(a, width) < _signed(b, width))
    elif op == "SLTU":
        y = int(a < b)
    elif op == "PASS_A":
        y = a
    elif op == "PASS_B":
        y = b
    else:  # NOP
        y = 0
    return {
        "y": y,
        "zero": int(y == 0),
        "lt": int(_signed(a, width) < _signed(b, width)),
        "ltu": int(a < b),
        "carry": carry,
    }


_BOUNDARIES = (0x00, 0x01, 0x7F, 0x80, 0xFF)
_PAIRS = [(a, b) for a in _BOUNDARIES for b in _BOUNDARIES]


@pytest.mark.parametrize("op", AVAIL_OPS)
@pytest.mark.parametrize("a,b", _PAIRS)
def test_operation_matrix(a, b, op):
    assert _run(8, a, b, op) == _reference(op, a, b, 8)


def test_signed_vs_unsigned_min_max():
    # 0x80 is the signed minimum, 0xFF the signed maximum negative value.
    assert _run(8, 0x80, 0x7F, "SLT")["y"] == 1
    assert _run(8, 0x80, 0x7F, "SLTU")["y"] == 0
    assert _run(8, 0xFF, 0x01, "SLT")["y"] == 1  # -1 < 1
    assert _run(8, 0xFB, 0x03, "SLT")["y"] == 1  # -5 < 3
    assert _run(8, 0xFB, 0x03, "SLTU")["y"] == 0


def test_carry_and_borrow():
    add = _run(8, 0xFF, 0x01, "ADD")
    assert (add["y"], add["carry"]) == (0x00, 1)
    sub = _run(8, 0x00, 0x01, "SUB")
    assert (sub["y"], sub["carry"]) == (0xFF, 1)
    no_carry = _run(8, 0x01, 0x01, "ADD")
    assert no_carry["carry"] == 0


def test_zero_flag():
    assert _run(8, 0x2A, 0x2A, "XOR")["zero"] == 1
    assert _run(8, 0x00, 0x00, "ADD")["zero"] == 1
    assert _run(8, 0x01, 0x00, "ADD")["zero"] == 0


def test_pass_through():
    assert _run(8, 0x5A, 0xA5, "PASS_A")["y"] == 0x5A
    assert _run(8, 0x5A, 0xA5, "PASS_B")["y"] == 0xA5


def test_nop_is_zero():
    assert _run(8, 0xFF, 0xFF, "NOP")["y"] == 0


def test_disabled_op_is_removed():
    y = _run(8, 0x05, 0x03, "SUB", ops=["ADD"])
    assert y["y"] == 0


def test_flag_subset_removes_port():
    alu = Alu(width=8, flags=["zero"])
    names = alu.ports().names
    assert "zero" in names
    assert "lt" not in names


def test_narrow_width_masks():
    assert _run(4, 0x0F, 0x01, "ADD")["y"] == 0x0
    assert _run(4, 0x0F, 0x01, "ADD")["carry"] == 1
    assert _run(4, 0x0F, 0x0F, "SUB")["y"] == 0x0
