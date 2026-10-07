"""Independent RVC oracle from the official ``riscv-opcodes`` tables.

Unlike ``decompress`` (our own transcription of the spec), these checks are
derived from the official encoding tables (``extensions/rv_c``, ``rv32_c``,
``rv_i``), so they are an **independent** reference for:

* **encoding classification / legality patterns** — every legal compressed
  encoding must be a named C instruction in the table, and every non-C pattern
  must be rejected; and
* the **opcode/funct fields** of the expansion — the produced 32-bit word must
  decode, via the base table, to the expected base instruction.

Not covered here (needs a semantic oracle such as binutils/Spike): the
immediate/register *values*, and the reserved-value constraints that the
opcode tables do not encode.
"""

from myhdl_addons.riscv.rvc import decompress

# --- official tables (vendored excerpts) ---------------------------------
#
# Source: riscv/riscv-opcodes (branch ``master``):
#   https://github.com/riscv/riscv-opcodes/blob/master/extensions/rv_c
#   https://github.com/riscv/riscv-opcodes/blob/master/extensions/rv32_c
#   https://github.com/riscv/riscv-opcodes/blob/master/extensions/rv_i
#   https://github.com/riscv/riscv-opcodes/blob/master/extensions/rv32_i
# Each excerpt below is copied verbatim from the indicated file; only the
# instruction lines are kept (upstream comment/blank lines dropped).  The
# C -> base expansion encoded by ``_C_TO_BASE`` is not from a table: it is
# hand-authored from the "C" standard-extension chapter of "The RISC-V
# Instruction Set Manual, Volume I: Unprivileged ISA".

# extensions/rv_c -- all 23 instruction lines, verbatim (four quadrants).
_RV_C = """
c.addi4spn rd_p c_nzuimm10              1..0=0 15..13=0
c.lw rd_p rs1_p c_uimm7lo c_uimm7hi     1..0=0 15..13=2
c.sw rs1_p rs2_p c_uimm7lo c_uimm7hi    1..0=0 15..13=6
c.nop c_nzimm6hi c_nzimm6lo              1..0=1 15..13=0 11..7=0
c.addi rd_rs1_n0 c_nzimm6lo c_nzimm6hi   1..0=1 15..13=0
c.li rd_n0 c_imm6lo c_imm6hi             1..0=1 15..13=2
c.addi16sp c_nzimm10hi c_nzimm10lo       1..0=1 15..13=3 11..7=2
c.lui rd_n2 c_nzimm18hi c_nzimm18lo      1..0=1 15..13=3
c.andi rd_rs1_p c_imm6hi c_imm6lo        1..0=1 15..13=4 11..10=2
c.sub rd_rs1_p rs2_p                     1..0=1 15..13=4 12..10=0b011 6..5=0
c.xor rd_rs1_p rs2_p                     1..0=1 15..13=4 12..10=0b011 6..5=1
c.or rd_rs1_p rs2_p                      1..0=1 15..13=4 12..10=0b011 6..5=2
c.and rd_rs1_p rs2_p                     1..0=1 15..13=4 12..10=0b011 6..5=3
c.j c_imm12                              1..0=1 15..13=5
c.beqz rs1_p c_bimm9lo c_bimm9hi         1..0=1 15..13=6
c.bnez rs1_p c_bimm9lo c_bimm9hi         1..0=1 15..13=7
c.lwsp rd_n0 c_uimm8sphi c_uimm8splo     1..0=2 15..13=2
c.jr rs1_n0                              1..0=2 15..13=4 12=0 6..2=0
c.mv rd_n0 c_rs2_n0                      1..0=2 15..13=4 12=0
c.ebreak                                 1..0=2 15..13=4 12=1 11..2=0
c.jalr c_rs1_n0                          1..0=2 15..13=4 12=1 6..2=0
c.add rd_rs1_n0 c_rs2_n0                 1..0=2 15..13=4 12=1
c.swsp c_rs2 c_uimm8sp_s                 1..0=2 15..13=6
"""

# extensions/rv32_c -- vendored excerpt: ``c.jal`` plus the plain
# c.srli/c.srai/c.slli ``$pseudo_op`` lines.  The upstream ``_rv32`` alias
# variants are omitted; they carry identical mask/match so classification is
# unaffected.  The parser takes ``$pseudo_op``'s ``tokens[2]`` as the name,
# dropping the ``rv64_c::<orig>`` prefix in ``tokens[1]``.
_RV32_C = """
c.jal c_imm12              1..0=1 15..13=1
$pseudo_op rv64_c::c.srli c.srli rd_rs1_p c_nzuimm5  1..0=1 15..13=4 12..10=0
$pseudo_op rv64_c::c.srai c.srai rd_rs1_p c_nzuimm5  1..0=1 15..13=4 12..10=1
$pseudo_op rv64_c::c.slli c.slli rd_rs1_n0 c_nzuimm6lo  1..0=2 15..12=0
"""

# extensions/rv_i -- vendored excerpt: only the base instructions that the C
# expansions may decode to (plus ``ebreak``).
_RV_I = """
lui     rd imm20 6..2=0x0D 1..0=3
jal     rd jimm20                          6..2=0x1b 1..0=3
jalr    rd rs1 imm12              14..12=0 6..2=0x19 1..0=3
beq     bimm12hi rs1 rs2 bimm12lo 14..12=0 6..2=0x18 1..0=3
bne     bimm12hi rs1 rs2 bimm12lo 14..12=1 6..2=0x18 1..0=3
lw      rd rs1       imm12 14..12=2 6..2=0x00 1..0=3
sw      imm12hi rs1 rs2 imm12lo 14..12=2 6..2=0x08 1..0=3
addi    rd rs1 imm12           14..12=0 6..2=0x04 1..0=3
andi    rd rs1 imm12           14..12=7 6..2=0x04 1..0=3
add     rd rs1 rs2 31..25=0  14..12=0 6..2=0x0C 1..0=3
sub     rd rs1 rs2 31..25=32 14..12=0 6..2=0x0C 1..0=3
xor     rd rs1 rs2 31..25=0  14..12=4 6..2=0x0C 1..0=3
or      rd rs1 rs2 31..25=0  14..12=6 6..2=0x0C 1..0=3
and     rd rs1 rs2 31..25=0  14..12=7 6..2=0x0C 1..0=3
ebreak   31..20=0x001 19..7=0 6..2=0x1C 1..0=3
"""

# extensions/rv32_i, the RV32I shifts (5-bit ``shamtw``), taken from the
# upstream lines:
#   $pseudo_op rv64_i::slli slli rd rs1 shamtw ...
#   $pseudo_op rv64_i::srli srli rd rs1 shamtw ...
#   $pseudo_op rv64_i::srai srai rd rs1 shamtw ...
# with the ``$pseudo_op rv64_i::<orig>`` prefix stripped.  These are OP-IMM
# (funct3 1/5; srai funct7 = 0x20 = 32 decimal).
_BASE_EXTRA = """
slli rd rs1 shamtw 31..25=0  14..12=1 6..2=0x04 1..0=3
srli rd rs1 shamtw 31..25=0  14..12=5 6..2=0x04 1..0=3
srai rd rs1 shamtw 31..25=32 14..12=5 6..2=0x04 1..0=3
"""

# Hand-authored (not an opcode-table excerpt): each C instruction maps to the
# base instruction its 32-bit expansion must decode to, per the expansion
# rules in the "C" standard-extension chapter of the RISC-V unprivileged ISA
# manual (e.g. c.jr/c.jalr -> jalr, c.mv/c.add -> add, c.nop/c.addi/c.li/
# c.addi16sp -> addi, c.lui -> lui, c.slli/srli/srai -> slli/srli/srai).
_C_TO_BASE = {
    "c.addi4spn": "addi",
    "c.lw": "lw",
    "c.sw": "sw",
    "c.nop": "addi",
    "c.addi": "addi",
    "c.li": "addi",
    "c.addi16sp": "addi",
    "c.lui": "lui",
    "c.andi": "andi",
    "c.sub": "sub",
    "c.xor": "xor",
    "c.or": "or",
    "c.and": "and",
    "c.j": "jal",
    "c.beqz": "beq",
    "c.bnez": "bne",
    "c.lwsp": "lw",
    "c.jr": "jalr",
    "c.mv": "add",
    "c.ebreak": "ebreak",
    "c.jalr": "jalr",
    "c.add": "add",
    "c.swsp": "sw",
    "c.jal": "jal",
    "c.srli": "srli",
    "c.srai": "srai",
    "c.slli": "slli",
}


def _parse(text, *, c_only):
    entries = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        if tokens[0] == "$pseudo_op":
            name, const = tokens[2], tokens[3:]
        else:
            name, const = tokens[0], tokens[1:]
        if c_only and not name.startswith("c."):
            continue
        mask = 0
        match = 0
        for token in const:
            if "=" not in token:
                continue
            lhs, value_text = token.split("=", 1)
            if ".." in lhs:
                hi_text, lo_text = lhs.split("..")
                hi, lo = int(hi_text), int(lo_text)
            else:
                hi = lo = int(lhs)
            field_mask = ((1 << (hi - lo + 1)) - 1) << lo
            mask |= field_mask
            match |= (int(value_text, 0) << lo) & field_mask
        entries.append((name, mask, match))
    return entries


_C_ENTRIES = _parse(_RV_C, c_only=True) + _parse(_RV32_C, c_only=True)
_BASE_ENTRIES = _parse(_RV_I, c_only=False) + _parse(_BASE_EXTRA, c_only=False)


def _classify(entries, value):
    for name, mask, match in entries:
        if (value & mask) == match:
            return name
    return None


def _classify_c(instr):
    return _classify(_C_ENTRIES, instr)


def _decode32(word):
    return _classify(_BASE_ENTRIES, word)


def test_oracle_covers_all_expansions_by_opcode():
    # every encoding our decompressor accepts is a named C instruction whose
    # 32-bit expansion decodes (base table) to the expected base instruction
    for instr in range(1 << 16):
        word, illegal = decompress(instr)
        if illegal:
            continue
        c_name = _classify_c(instr)
        assert c_name is not None, f"{instr:#06x} accepted but not a C encoding"
        expected = _C_TO_BASE[c_name]
        assert _decode32(word) == expected, (
            f"{instr:#06x} ({c_name}) -> {word:#010x} decodes as "
            f"{_decode32(word)!r}, expected {expected!r}"
        )


def test_oracle_rejects_every_non_c_pattern():
    # any 16-bit pattern that is not a C instruction encoding must be rejected
    for instr in range(1 << 16):
        if _classify_c(instr) is None:
            assert decompress(instr)[1] is True, (
                f"{instr:#06x} is not a C encoding but was accepted"
            )


def test_oracle_table_entries_are_sane():
    assert len(_C_ENTRIES) >= 27
    assert {name for name, _, _ in _C_ENTRIES} >= set(_C_TO_BASE)
    for name in _C_TO_BASE.values():
        assert any(entry[0] == name for entry in _BASE_ENTRIES), name
