"""``InstructionDecoder`` control decoding and illegal detection.

Covers ``RC-FR-020/021/024/088`` (all base instruction classes, unknown
encodings, compressed words) and ``RC-FR-056`` (registry-driven legality).
"""

from myhdl import StopSimulation, always_comb, block, delay, instance

from myhdl_addons.components import AVAIL_OPS
from myhdl_addons.riscv import (
    AVAIL_IMM_TYPES,
    Extension,
    ExtensionRegistry,
    InstructionDecoder,
)

_ALU = {name: code for code, name in enumerate(AVAIL_OPS)}
_IMM = {name: code for code, name in enumerate(AVAIL_IMM_TYPES)}

SLL, SRL, SRA = 0, 1, 2  # BarrelShifter mode codes


def _r(f7, rs2, rs1, f3, rd, op=0x33):
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _i(imm, rs1, f3, rd, op=0x13):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _s(imm, rs2, rs1, f3, op=0x23):
    imm &= 0xFFF
    return (
        ((imm >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | ((imm & 0x1F) << 7)
        | op
    )


def _b(imm, rs2, rs1, f3, op=0x63):
    imm &= 0x1FFF
    return (
        (((imm >> 12) & 1) << 31)
        | (((imm >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | (((imm >> 1) & 0xF) << 8)
        | (((imm >> 11) & 1) << 7)
        | op
    )


def _u(imm, rd, op=0x37):
    return ((imm & 0xFFFFF) << 12) | (rd << 7) | op


def _j(imm, rd, op=0x6F):
    imm &= 0x1FFFFF
    return (
        (((imm >> 20) & 1) << 31)
        | (((imm >> 1) & 0x3FF) << 21)
        | (((imm >> 11) & 1) << 20)
        | (((imm >> 12) & 0xFF) << 12)
        | (rd << 7)
        | op
    )


# (instruction, subset of expected control signals)
_CASES = [
    (
        _u(0x12345, 1),
        {
            "reg_write": 1,
            "alu_b_imm": 1,
            "alu_op": _ALU["PASS_B"],
            "imm_sel": _IMM["U"],
            "rd": 1,
            "illegal": 0,
        },
    ),
    (
        _u(0, 1, op=0x17),
        {
            "reg_write": 1,
            "alu_a_pc": 1,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["U"],
            "illegal": 0,
        },
    ),
    (
        _j(8, 1),
        {
            "reg_write": 1,
            "jump": 1,
            "alu_a_pc": 1,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["J"],
            "illegal": 0,
        },
    ),
    (
        _i(0, 2, 0, 1, op=0x67),
        {
            "reg_write": 1,
            "jump": 1,
            "jalr": 1,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["I"],
            "rs1": 2,
            "illegal": 0,
        },
    ),
    (
        _b(8, 2, 1, 0),
        {
            "branch": 1,
            "branch_op": 0,
            "alu_a_pc": 1,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["B"],
            "illegal": 0,
        },
    ),
    (_b(8, 2, 1, 1), {"branch": 1, "branch_op": 1, "illegal": 0}),
    (
        _i(0, 2, 2, 1, op=0x03),
        {
            "reg_write": 1,
            "mem_read": 1,
            "mem_size": 2,
            "mem_unsigned": 0,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["I"],
            "illegal": 0,
        },
    ),
    (_i(0, 2, 0, 1, op=0x03), {"mem_read": 1, "mem_size": 0, "illegal": 0}),
    (_i(0, 2, 4, 1, op=0x03), {"mem_read": 1, "mem_unsigned": 1, "illegal": 0}),
    (
        _s(4, 2, 1, 2),
        {
            "mem_write": 1,
            "mem_size": 2,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["S"],
            "illegal": 0,
        },
    ),
    (
        _i(0, 2, 0, 1),
        {
            "reg_write": 1,
            "alu_b_imm": 1,
            "alu_op": _ALU["ADD"],
            "imm_sel": _IMM["I"],
            "illegal": 0,
        },
    ),
    (
        _r(0, 3, 2, 0, 1),
        {
            "reg_write": 1,
            "alu_b_imm": 0,
            "alu_op": _ALU["ADD"],
            "rs1": 2,
            "rs2": 3,
            "rd": 1,
            "illegal": 0,
        },
    ),
    (_r(0x20, 3, 2, 0, 1), {"alu_op": _ALU["SUB"], "illegal": 0}),
    (_r(0, 3, 2, 7, 1), {"alu_op": _ALU["AND"], "illegal": 0}),
    (_r(0, 3, 2, 2, 1), {"alu_op": _ALU["SLT"], "illegal": 0}),
    (_r(0, 3, 2, 3, 1), {"alu_op": _ALU["SLTU"], "illegal": 0}),
    (
        _i(1, 2, 1, 1),
        {"shift": 1, "shift_mode": SLL, "alu_b_imm": 1, "reg_write": 1, "illegal": 0},
    ),
    (_i(1, 2, 5, 1), {"shift": 1, "shift_mode": SRL, "illegal": 0}),
    (_i(0x401, 2, 5, 1), {"shift": 1, "shift_mode": SRA, "illegal": 0}),
    (
        _r(0, 3, 2, 1, 1),
        {"shift": 1, "shift_mode": SLL, "alu_b_imm": 0, "reg_write": 1, "illegal": 0},
    ),
    (_r(0x20, 3, 2, 5, 1), {"shift": 1, "shift_mode": SRA, "illegal": 0}),
    (0x0000000F, {"fence": 1, "illegal": 0}),  # fence
    (0x0000100F, {"fence": 1, "illegal": 0}),  # fence.i
    (0x00000073, {"ecall": 1, "illegal": 0}),
    (0x00100073, {"ebreak": 1, "illegal": 0}),
]

_ILLEGAL = [
    0x00000000,  # compressed (op 00)
    0x00000001,  # compressed (op 01)
    0x00000002,  # compressed (op 10)
    0xFFFFFFFF,  # compressed (op 11 ... but opcode 0x7F)
    0x0000007F,  # unknown opcode 0x7F
    0x0000000B,  # unknown opcode 0x0B
    _i(0x021, 2, 1, 1),  # slli with funct7 != 0
    _i(0x081, 2, 5, 1),  # srli with reserved funct7
    _r(0x40, 3, 2, 1, 1),  # sll with funct7 != 0
    _r(0x40, 3, 2, 0, 1),  # add with reserved funct7
    _b(0, 1, 1, 2),  # branch funct3 = 010 (reserved)
    _b(0, 1, 1, 3),  # branch funct3 = 011 (reserved)
    _i(0, 1, 3, 1, op=0x03),  # load funct3 = 011 (reserved)
    _i(0, 1, 6, 1, op=0x03),  # load funct3 = 110 (reserved)
    _s(0, 1, 1, 4),  # store funct3 = 100 (reserved)
    0x0000200F,  # misc-mem funct3 = 010 (reserved)
    _i(2, 0, 0, 0, op=0x73),  # system imm != 0/1
    _i(0, 0, 0, 1, op=0x73),  # ecall with rd != 0
    0x00100073 | (1 << 15),  # ebreak with rs1 != 0
]

_CASE_INSTRS = [instr for instr, _ in _CASES]
_ALL_INSTRS = _CASE_INSTRS + _ILLEGAL


@block
def _decode_tb(comp, instrs, results):
    ports = comp.ports()
    dut = comp.hdl(ports)

    @instance
    def stim():
        for instr in instrs:
            ports.instr.next = instr
            yield delay(1)
            results.append(
                {name: int(ports[name]) for name in ports.names if name != "instr"}
            )
        raise StopSimulation

    return dut, stim


def _run(instrs, comp=None):
    comp = comp if comp is not None else InstructionDecoder()
    results = []
    _decode_tb(comp, instrs, results).run_sim()
    return results


def test_control_signals():
    outputs = _run(_CASE_INSTRS)
    for (instr, expected), got in zip(_CASES, outputs):
        for name, value in expected.items():
            assert got[name] == value, f"{instr:#010x}: {name}={got[name]} != {value}"


def test_illegal_encodings():
    outputs = _run(_ILLEGAL)
    for instr, got in zip(_ILLEGAL, outputs):
        assert got["illegal"] == 1, f"{instr:#010x} should be illegal"


def test_register_fields_always_exposed():
    # rd/rs1/rs2 are the raw instruction fields regardless of legality
    instr = _r(0, 3, 2, 0, 5)
    got = _run([instr])[0]
    assert (got["rd"], got["rs1"], got["rs2"]) == (5, 2, 3)
    got = _run([0x00000000])[0]  # illegal compressed still exposes fields
    assert (got["rd"], got["rs1"], got["rs2"]) == (0, 0, 0)


_ADD = _ALU["ADD"]
_IMM_I = _IMM["I"]


class _DecodeExt(Extension):
    """Minimal decode extension: claims one opcode and forces ``ADD x0, x0``."""

    def __init__(self, name="x", mask=0x7F, value=0x0B, priority=0):
        self.name = name
        self.priority = priority
        self._claim = (mask, value)

    def claims(self):
        return (self._claim,)

    @block
    def decode_stage(self, context):
        instr = context.instr
        matched = context.matched
        illegal = context.illegal
        rd = context.rd
        rs1 = context.rs1
        rs2 = context.rs2
        reg_write = context.reg_write
        alu_a_pc = context.alu_a_pc
        alu_b_imm = context.alu_b_imm
        alu_op = context.alu_op
        shift = context.shift
        shift_mode = context.shift_mode
        imm_sel = context.imm_sel
        mem_read = context.mem_read
        mem_write = context.mem_write
        mem_size = context.mem_size
        mem_unsigned = context.mem_unsigned
        branch = context.branch
        branch_op = context.branch_op
        jump = context.jump
        jalr = context.jalr
        ecall = context.ecall
        ebreak = context.ebreak
        fence = context.fence
        mask = self._claim[0]
        value = self._claim[1]

        @always_comb
        def decode():
            matched.next = (instr & mask) == value
            illegal.next = 0
            rd.next = instr[12:7]
            rs1.next = instr[20:15]
            rs2.next = instr[25:20]
            reg_write.next = 1
            alu_a_pc.next = 0
            alu_b_imm.next = 0
            alu_op.next = _ADD
            shift.next = 0
            shift_mode.next = 0
            imm_sel.next = _IMM_I
            mem_read.next = 0
            mem_write.next = 0
            mem_size.next = 0
            mem_unsigned.next = 0
            branch.next = 0
            branch_op.next = 0
            jump.next = 0
            jalr.next = 0
            ecall.next = 0
            ebreak.next = 0
            fence.next = 0

        return decode


def test_decode_stage_extension_extends_control():
    reg = ExtensionRegistry([_DecodeExt()])
    reg.select(["x"])
    dec = InstructionDecoder(registry=reg)
    assert dec.as_dict()["extensions"] == ("x",)
    got = _run([0x0000000B], dec)[0]  # previously illegal opcode 0x0B
    assert got["illegal"] == 0
    assert got["reg_write"] == 1
    assert got["alu_op"] == _ADD


def test_decode_stage_extension_does_not_regress_base():
    # an encoding the extension does not claim still uses the base decode
    reg = ExtensionRegistry([_DecodeExt()])
    reg.select(["x"])
    dec = InstructionDecoder(registry=reg)
    got = _run([_u(0, 1)], dec)[0]  # lui x1, 0
    assert got["illegal"] == 0
    assert got["alu_op"] == _ALU["PASS_B"]


def test_unselected_decode_extensions_are_zero_overhead():
    reg = ExtensionRegistry([_DecodeExt()])  # never selected
    dec = InstructionDecoder(registry=reg)
    assert dec.as_dict()["extensions"] == ()
    assert _run([0x0000000B], dec)[0]["illegal"] == 1
