"""RVC (compressed) decompressor (``RC-FR-040/042/044/047``).

Expands a 16-bit RVC instruction to its 32-bit RV32I equivalent so the primary
decoder/datapath are reused unchanged (``RC-FR-042``).  Only the RV32 C subset
is handled — ``Zca`` plus RV32-only ``c.jal``; F/D compressed forms and other
reserved encodings are reported via the ``illegal`` output.

:func:`decompress` is the pure-Python reference (a golden function used by the
tests); :class:`RvcDecompressor` is the synthesizable, convertible
implementation.  The block is purely combinational.

MyHDL note: ``sig[i:j]`` selects bits ``j .. i-1`` (half-open), so an inclusive
field ``bits[hi:lo]`` is written ``sig[hi + 1:lo]`` (e.g. the low 8 bits are
``sig[8:]``).  A single index ``sig[k]`` yields a Python ``bool``.
"""

from myhdl import Signal, always_comb, block, concat, intbv

from ..common.config import ComponentBase
from ..common.views import SignalView
from .extensions import Extension, ExtensionRegistry

__all__ = [
    "CExtension",
    "RvcDecompressor",
    "decompress",
    "default_registry",
    "is_compressed",
]

_OP_LUI = 0x37
_OP_JAL = 0x6F
_OP_JALR = 0x67
_OP_BRANCH = 0x63
_OP_LOAD = 0x03
_OP_STORE = 0x23
_OP_IMM = 0x13
_OP = 0x33
_OP_SYSTEM = 0x73
_EBREAK = 0x00100073


def _sext(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _r(f7: int, rs2: int, rs1: int, f3: int, rd: int) -> int:
    return (
        ((f7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((f3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | _OP
    )


def _i(imm: int, rs1: int, f3: int, rd: int, opc: int) -> int:
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((f3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | opc
    )


def _s(imm: int, rs2: int, rs1: int, f3: int) -> int:
    imm &= 0xFFF
    return (
        (((imm >> 5) & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((f3 & 0x7) << 12)
        | ((imm & 0x1F) << 7)
        | _OP_STORE
    )


def _b(imm: int, rs2: int, rs1: int, f3: int) -> int:
    imm &= 0x1FFF
    return (
        (((imm >> 12) & 1) << 31)
        | (((imm >> 5) & 0x3F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((f3 & 0x7) << 12)
        | (((imm >> 1) & 0xF) << 8)
        | (((imm >> 11) & 1) << 7)
        | _OP_BRANCH
    )


def _u(imm20: int, rd: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | _OP_LUI


def _j(imm: int, rd: int) -> int:
    imm &= 0x1FFFFF
    return (
        (((imm >> 20) & 1) << 31)
        | (((imm >> 1) & 0x3FF) << 21)
        | (((imm >> 11) & 1) << 20)
        | (((imm >> 12) & 0xFF) << 12)
        | ((rd & 0x1F) << 7)
        | _OP_JAL
    )


def _cj(instr: int) -> int:
    return _sext(
        (((instr >> 12) & 1) << 11)
        | (((instr >> 11) & 1) << 4)
        | (((instr >> 9) & 0x3) << 8)
        | (((instr >> 8) & 1) << 10)
        | (((instr >> 7) & 1) << 6)
        | (((instr >> 6) & 1) << 7)
        | (((instr >> 3) & 0x7) << 1)
        | (((instr >> 2) & 1) << 5),
        12,
    )


def _cb(instr: int) -> int:
    return _sext(
        (((instr >> 12) & 1) << 8)
        | (((instr >> 10) & 0x3) << 3)
        | (((instr >> 5) & 0x3) << 6)
        | (((instr >> 3) & 0x3) << 1)
        | (((instr >> 2) & 1) << 5),
        9,
    )


def decompress(instr: int) -> tuple[int, bool]:
    """Return ``(word32, illegal)`` for the 16-bit compressed *instr*."""
    instr &= 0xFFFF
    op = instr & 0x3
    f3 = (instr >> 13) & 0x7
    rd = (instr >> 7) & 0x1F
    rs2 = (instr >> 2) & 0x1F
    rd_p = 8 | ((instr >> 2) & 0x7)
    rs1_p = 8 | ((instr >> 7) & 0x7)
    rs2_p = 8 | ((instr >> 2) & 0x7)
    ci_imm = _sext((((instr >> 12) & 1) << 5) | ((instr >> 2) & 0x1F), 6)

    if op == 0b00:
        if f3 == 0b000:  # c.addi4spn
            nzuimm = (
                (((instr >> 11) & 0x3) << 4)
                | (((instr >> 7) & 0xF) << 6)
                | (((instr >> 6) & 1) << 2)
                | (((instr >> 5) & 1) << 3)
            )
            if nzuimm == 0:
                return 0, True
            return _i(nzuimm, 2, 0, rd_p, _OP_IMM), False
        if f3 == 0b010:  # c.lw
            uimm = (
                (((instr >> 10) & 0x7) << 3)
                | (((instr >> 6) & 1) << 2)
                | (((instr >> 5) & 1) << 6)
            )
            return _i(uimm, rs1_p, 2, rd_p, _OP_LOAD), False
        if f3 == 0b110:  # c.sw
            uimm = (
                (((instr >> 10) & 0x7) << 3)
                | (((instr >> 6) & 1) << 2)
                | (((instr >> 5) & 1) << 6)
            )
            return _s(uimm, rs2_p, rs1_p, 2), False
        return 0, True

    if op == 0b01:
        if f3 == 0b000:  # c.nop / c.addi
            return _i(ci_imm, rd, 0, rd, _OP_IMM), False
        if f3 == 0b001:  # c.jal (RV32)
            return _j(_cj(instr), 1), False
        if f3 == 0b010:  # c.li
            return _i(ci_imm, 0, 0, rd, _OP_IMM), False
        if f3 == 0b011:  # c.addi16sp / c.lui
            if rd == 0:
                return 0, True
            if rd == 2:
                nzimm = (
                    (((instr >> 12) & 1) << 9)
                    | (((instr >> 6) & 1) << 4)
                    | (((instr >> 5) & 1) << 6)
                    | (((instr >> 3) & 0x3) << 7)
                    | (((instr >> 2) & 1) << 5)
                )
                if nzimm == 0:
                    return 0, True
                return _i(_sext(nzimm, 10), 2, 0, 2, _OP_IMM), False
            if ci_imm == 0:
                return 0, True
            return _u(ci_imm & 0xFFFFF, rd), False
        if f3 == 0b100:  # srli/srai/andi and sub/xor/or/and
            sub = (instr >> 10) & 0x3
            if sub == 0b00:  # c.srli
                if (instr >> 12) & 1:
                    return 0, True
                return _i((instr >> 2) & 0x1F, rs1_p, 5, rs1_p, _OP_IMM), False
            if sub == 0b01:  # c.srai
                if (instr >> 12) & 1:
                    return 0, True
                shamt5 = 0x400 | ((instr >> 2) & 0x1F)
                return _i(shamt5, rs1_p, 5, rs1_p, _OP_IMM), False
            if sub == 0b10:  # c.andi
                return _i(ci_imm, rs1_p, 7, rs1_p, _OP_IMM), False
            if (instr >> 12) & 1:  # c.sub/.xor/.or/.and require funct6 = 100011
                return 0, True
            op2 = (instr >> 5) & 0x3  # c.sub / c.xor / c.or / c.and
            f3c = (0, 4, 6, 7)[op2]
            f7 = 0x20 if op2 == 0 else 0
            return _r(f7, rs2_p, rs1_p, f3c, rd_p), False
        if f3 == 0b101:  # c.j
            return _j(_cj(instr), 0), False
        if f3 in (0b110, 0b111):  # c.beqz / c.bnez
            return _b(_cb(instr), 0, rs1_p, f3 & 1), False
        return 0, True

    if op == 0b10:
        if f3 == 0b000:  # c.slli
            if (instr >> 12) & 1:
                return 0, True
            return _i((instr >> 2) & 0x1F, rd, 1, rd, _OP_IMM), False
        if f3 == 0b010:  # c.lwsp
            if rd == 0:
                return 0, True
            uimm = (
                (((instr >> 12) & 1) << 5)
                | (((instr >> 4) & 0x7) << 2)
                | (((instr >> 2) & 0x3) << 6)
            )
            return _i(uimm, 2, 2, rd, _OP_LOAD), False
        if f3 == 0b100:  # c.jr / c.mv / c.ebreak / c.jalr / c.add
            if (instr >> 12) & 1:
                if rs2 == 0:
                    if rd == 0:
                        return _EBREAK, False
                    return _i(0, rd, 0, 1, _OP_JALR), False
                return _r(0, rs2, rd, 0, rd), False
            if rs2 == 0:
                if rd == 0:
                    return 0, True
                return _i(0, rd, 0, 0, _OP_JALR), False
            return _r(0, rs2, 0, 0, rd), False
        if f3 == 0b110:  # c.swsp
            uimm = (((instr >> 9) & 0xF) << 2) | (((instr >> 7) & 0x3) << 6)
            return _s(uimm, rs2, 2, 2), False
        return 0, True

    return 0, True  # op == 0b11: not a compressed instruction


def is_compressed(instruction: int) -> bool:
    """Return whether *instruction* is a 16-bit (compressed) encoding.

    RISC-V marks compressed instructions with ``inst[1:0] != 2'b11``; a 32-bit
    instruction has ``inst[1:0] == 2'b11``.  When the C extension is disabled,
    any instruction for which this is true is illegal (``RC-FR-041``).
    """
    return (instruction & 0x3) != 0x3


class RvcDecompressor(ComponentBase):
    """Expand a 16-bit RVC instruction to its 32-bit form (``RC-FR-042``).

    Ports: ``instr_i`` (16 bits), ``instr_o`` (32 bits) and ``illegal`` (set for
    reserved/unsupported encodings and for the non-compressed ``op == 0b11``).
    Purely combinational.
    """

    def ports(self) -> SignalView:
        """Allocate and return the ``instr_i``/``instr_o``/``illegal`` view."""
        return SignalView(
            instr_i=Signal(intbv(0)[16:]),
            instr_o=Signal(intbv(0)[32:]),
            illegal=Signal(bool(0)),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the decompressor onto *ports* and return its instances."""
        i = ports.instr_i

        @always_comb
        def decompress_proc():
            ports.illegal.next = 1
            ports.instr_o.next = 0
            if i[2:0] == 0b00:
                if i[16:13] == 0b000:  # c.addi4spn
                    if i[13:5] != 0:
                        ports.instr_o.next = concat(
                            intbv(0)[2:],
                            i[11:7],  # inst[10:7]
                            i[13:11],  # inst[12:11]
                            i[6:5],  # inst[5]
                            i[7:6],  # inst[6]
                            intbv(0)[2:],
                            intbv(2)[5:],
                            intbv(0)[3:],
                            intbv(1)[2:],
                            i[5:2],
                            intbv(_OP_IMM)[7:],
                        )
                        ports.illegal.next = 0
                elif i[16:13] == 0b010:  # c.lw
                    ports.instr_o.next = concat(
                        intbv(0)[5:],
                        i[6:5],  # inst[5]
                        i[13:10],  # inst[12:10]
                        i[7:6],  # inst[6]
                        intbv(0)[2:],
                        intbv(1)[2:],
                        i[10:7],
                        intbv(2)[3:],
                        intbv(1)[2:],
                        i[5:2],
                        intbv(_OP_LOAD)[7:],
                    )
                    ports.illegal.next = 0
                elif i[16:13] == 0b110:  # c.sw
                    ports.instr_o.next = concat(
                        intbv(0)[5:],
                        i[6:5],  # inst[5]
                        i[13:12],  # inst[12]
                        intbv(1)[2:],
                        i[5:2],
                        intbv(1)[2:],
                        i[10:7],
                        intbv(2)[3:],
                        i[12:10],  # inst[11:10]
                        i[7:6],  # inst[6]
                        intbv(0)[2:],
                        intbv(_OP_STORE)[7:],
                    )
                    ports.illegal.next = 0
            elif i[2:0] == 0b01:
                if i[16:13] == 0b000:  # c.nop / c.addi
                    ports.instr_o.next = concat(
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],  # imm[11:5] = sign
                        i[7:2],  # imm[4:0]
                        i[12:7],  # rs1
                        intbv(0)[3:],
                        i[12:7],  # rd
                        intbv(_OP_IMM)[7:],
                    )
                    ports.illegal.next = 0
                elif i[16:13] == 0b010:  # c.li
                    ports.instr_o.next = concat(
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[7:2],
                        intbv(0)[5:],
                        intbv(0)[3:],
                        i[12:7],
                        intbv(_OP_IMM)[7:],
                    )
                    ports.illegal.next = 0
                elif i[16:13] == 0b011:  # c.addi16sp / c.lui
                    if i[12:7] == 2:  # c.addi16sp
                        if not i[12] and i[7:2] == 0:
                            ports.illegal.next = 1
                        else:
                            ports.instr_o.next = concat(
                                i[13:12],
                                i[13:12],
                                i[13:12],  # imm[11:9]
                                i[5:3],  # inst[4:3]
                                i[6:5],  # inst[5]
                                i[3:2],  # inst[2]
                                i[7:6],  # inst[6]
                                intbv(0)[4:],
                                intbv(2)[5:],
                                intbv(0)[3:],
                                intbv(2)[5:],
                                intbv(_OP_IMM)[7:],
                            )
                            ports.illegal.next = 0
                    elif i[12:7] != 0:  # c.lui
                        if not i[12] and i[7:2] == 0:
                            ports.illegal.next = 1
                        else:
                            ports.instr_o.next = concat(
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],
                                i[13:12],  # imm[19:6] sign
                                i[7:2],  # imm[4:0]
                                i[12:7],  # rd
                                intbv(_OP_LUI)[7:],
                            )
                            ports.illegal.next = 0
                elif i[16:13] == 0b100:  # srli/srai/andi and sub/xor/or/and
                    if i[12:10] == 0b00 and not i[12]:  # c.srli
                        ports.instr_o.next = concat(
                            intbv(0)[7:],
                            i[7:2],
                            intbv(1)[2:],
                            i[10:7],
                            intbv(5)[3:],
                            intbv(1)[2:],
                            i[10:7],
                            intbv(_OP_IMM)[7:],
                        )
                        ports.illegal.next = 0
                    elif i[12:10] == 0b01 and not i[12]:  # c.srai
                        ports.instr_o.next = concat(
                            intbv(0x20)[7:],
                            i[7:2],
                            intbv(1)[2:],
                            i[10:7],
                            intbv(5)[3:],
                            intbv(1)[2:],
                            i[10:7],
                            intbv(_OP_IMM)[7:],
                        )
                        ports.illegal.next = 0
                    elif i[12:10] == 0b10:  # c.andi
                        ports.instr_o.next = concat(
                            i[13:12],
                            i[13:12],
                            i[13:12],
                            i[13:12],
                            i[13:12],
                            i[13:12],
                            i[13:12],
                            i[7:2],
                            intbv(1)[2:],
                            i[10:7],
                            intbv(7)[3:],
                            intbv(1)[2:],
                            i[10:7],
                            intbv(_OP_IMM)[7:],
                        )
                        ports.illegal.next = 0
                    elif i[12:10] == 0b11 and not i[12]:  # c.sub/xor/or/and
                        if i[7:5] == 0b00:  # c.sub
                            ports.instr_o.next = concat(
                                intbv(0x20)[7:],
                                intbv(1)[2:],
                                i[5:2],  # rs2_p
                                intbv(1)[2:],
                                i[10:7],  # rs1_p
                                intbv(0)[3:],
                                intbv(1)[2:],
                                i[5:2],  # rd_p
                                intbv(_OP)[7:],
                            )
                        elif i[7:5] == 0b01:  # c.xor
                            ports.instr_o.next = concat(
                                intbv(0)[7:],
                                intbv(1)[2:],
                                i[5:2],  # rs2_p
                                intbv(1)[2:],
                                i[10:7],  # rs1_p
                                intbv(4)[3:],
                                intbv(1)[2:],
                                i[5:2],  # rd_p
                                intbv(_OP)[7:],
                            )
                        elif i[7:5] == 0b10:  # c.or
                            ports.instr_o.next = concat(
                                intbv(0)[7:],
                                intbv(1)[2:],
                                i[5:2],  # rs2_p
                                intbv(1)[2:],
                                i[10:7],  # rs1_p
                                intbv(6)[3:],
                                intbv(1)[2:],
                                i[5:2],  # rd_p
                                intbv(_OP)[7:],
                            )
                        else:  # c.and
                            ports.instr_o.next = concat(
                                intbv(0)[7:],
                                intbv(1)[2:],
                                i[5:2],  # rs2_p
                                intbv(1)[2:],
                                i[10:7],  # rs1_p
                                intbv(7)[3:],
                                intbv(1)[2:],
                                i[5:2],  # rd_p
                                intbv(_OP)[7:],
                            )
                        ports.illegal.next = 0
                elif i[16:13] == 0b001:  # c.jal
                    ports.instr_o.next = concat(
                        i[13:12],  # imm[20]
                        # imm[10:1]
                        i[9:8],
                        i[11:9],
                        i[7:6],
                        i[8:7],
                        i[3:2],
                        i[12:11],
                        i[6:3],
                        i[13:12],  # imm[11]
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],  # imm[19:12]
                        intbv(1)[5:],  # rd = 1
                        intbv(_OP_JAL)[7:],
                    )
                    ports.illegal.next = 0
                elif i[16:13] == 0b101:  # c.j
                    ports.instr_o.next = concat(
                        i[13:12],  # imm[20]
                        # imm[10:1]
                        i[9:8],
                        i[11:9],
                        i[7:6],
                        i[8:7],
                        i[3:2],
                        i[12:11],
                        i[6:3],
                        i[13:12],  # imm[11]
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],
                        i[13:12],  # imm[19:12]
                        intbv(0)[5:],  # rd = 0
                        intbv(_OP_JAL)[7:],
                    )
                    ports.illegal.next = 0
                elif i[16:13] == 0b110 or i[16:13] == 0b111:  # c.beqz / c.bnez
                    ports.instr_o.next = concat(
                        i[13:12],  # imm[12]
                        i[13:12],
                        i[13:12],
                        i[13:12],  # imm[10:8] sign
                        i[7:5],  # inst[6:5]
                        i[3:2],  # inst[2]
                        intbv(0)[5:],  # rs2 = 0
                        intbv(1)[2:],
                        i[10:7],
                        intbv(0)[2:],
                        i[14:13],  # funct3: beq=000, bne=001
                        i[12:10],  # inst[11:10]
                        i[5:3],  # inst[4:3]
                        i[13:12],  # imm[11]
                        intbv(_OP_BRANCH)[7:],
                    )
                    ports.illegal.next = 0
            elif i[2:0] == 0b10:
                if i[16:13] == 0b000:  # c.slli
                    if not i[12]:
                        ports.instr_o.next = concat(
                            intbv(0)[7:],
                            i[7:2],
                            i[12:7],
                            intbv(1)[3:],
                            i[12:7],
                            intbv(_OP_IMM)[7:],
                        )
                        ports.illegal.next = 0
                elif i[16:13] == 0b010:  # c.lwsp
                    if i[12:7] != 0:
                        ports.instr_o.next = concat(
                            intbv(0)[4:],
                            i[4:2],  # inst[3:2]
                            i[13:12],  # inst[12]
                            i[7:4],  # inst[6:4]
                            intbv(0)[2:],
                            intbv(2)[5:],
                            intbv(2)[3:],
                            i[12:7],
                            intbv(_OP_LOAD)[7:],
                        )
                        ports.illegal.next = 0
                elif i[16:13] == 0b100:
                    if i[12]:
                        if i[7:2] == 0:  # rs2 == 0
                            if i[12:7] == 0:  # c.ebreak
                                ports.instr_o.next = intbv(_EBREAK)[32:]
                                ports.illegal.next = 0
                            else:  # c.jalr
                                ports.instr_o.next = concat(
                                    intbv(0)[12:],
                                    i[12:7],
                                    intbv(0)[3:],
                                    intbv(1)[5:],
                                    intbv(_OP_JALR)[7:],
                                )
                                ports.illegal.next = 0
                        else:  # c.add
                            ports.instr_o.next = concat(
                                intbv(0)[7:],
                                i[7:2],
                                i[12:7],
                                intbv(0)[3:],
                                i[12:7],
                                intbv(_OP)[7:],
                            )
                            ports.illegal.next = 0
                    elif i[7:2] == 0:  # c.jr
                        if i[12:7] != 0:
                            ports.instr_o.next = concat(
                                intbv(0)[12:],
                                i[12:7],
                                intbv(0)[3:],
                                intbv(0)[5:],
                                intbv(_OP_JALR)[7:],
                            )
                            ports.illegal.next = 0
                    else:  # c.mv
                        ports.instr_o.next = concat(
                            intbv(0)[7:],
                            i[7:2],
                            intbv(0)[5:],
                            intbv(0)[3:],
                            i[12:7],
                            intbv(_OP)[7:],
                        )
                        ports.illegal.next = 0
                elif i[16:13] == 0b110:  # c.swsp
                    ports.instr_o.next = concat(
                        intbv(0)[4:],
                        i[9:7],  # inst[8:7]
                        i[13:12],  # inst[12]
                        i[7:2],  # rs2
                        intbv(2)[5:],
                        intbv(2)[3:],
                        i[12:9],  # inst[11:9]
                        intbv(0)[2:],
                        intbv(_OP_STORE)[7:],
                    )
                    ports.illegal.next = 0

        return decompress_proc


class CExtension(Extension):
    """The C (compressed) front-end ISA plug-in (``RC-FR-039/041``, Q17).

    C contributes a **front-end** stage only: the :class:`RvcDecompressor` is
    placed ahead of the shared RV32I decoder, so no 32-bit decode encodings are
    added and :meth:`claims` stays empty (Q7).  When the extension is not
    selected the registry builds no block, so C costs **zero logic**
    (``RC-FR-033``) and every compressed encoding is illegal (``RC-FR-041``).
    """

    name = "c"
    priority = 0

    def front_end(self, context: SignalView) -> list:
        """Elaborate the decompressor onto the front-end *context*.

        The context supplies the shared front-end signals ``instr_i`` (16-bit),
        ``instr_o`` (32-bit) and ``illegal`` (``RC-FR-042``); the decompressor
        drives the latter two from the first.
        """
        return [RvcDecompressor().hdl(context)]


def default_registry() -> ExtensionRegistry:
    """Return a registry with the built-in extensions registered (C)."""
    return ExtensionRegistry([CExtension()])
