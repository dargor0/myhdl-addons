"""RV32IC architectural ISS tests (``RC-FR-130``, Q22).

Plain-Python (non-HDL): instruction semantics, C decode parity with
``decompress``, faults, ``tohost``/``fromhost`` and the retire hook.
"""

from myhdl_addons.riscv import (
    CAUSE,
    MemoryImage,
    RV32ICIss,
    Retire,
    SignatureChecker,
    decompress,
)

_MASK = 0xFFFFFFFF

_OP_LUI = 0x37
_OP_AUIPC = 0x17
_OP_JAL = 0x6F
_OP_JALR = 0x67
_OP_BRANCH = 0x63
_OP_LOAD = 0x03
_OP_STORE = 0x23
_OP_IMM = 0x13
_OP = 0x33


def _i(imm, rs1, f3, rd, op=_OP_IMM):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op


def _r(f7, rs2, rs1, f3, rd):
    return (f7 << 25) | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | _OP


def _s(imm, rs2, rs1, f3):
    imm &= 0xFFF
    return (
        ((imm >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | ((imm & 0x1F) << 7)
        | _OP_STORE
    )


def _b(imm, rs2, rs1, f3):
    imm &= 0x1FFF
    return (
        (((imm >> 12) & 1) << 31)
        | (((imm >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (f3 << 12)
        | (((imm >> 1) & 0xF) << 8)
        | (((imm >> 11) & 1) << 7)
        | _OP_BRANCH
    )


def _u(imm, rd, op):
    return (imm & 0xFFFFF000) | (rd << 7) | op


def _j(imm, rd):
    imm &= 0x1FFFFF
    return (
        (((imm >> 20) & 1) << 31)
        | (((imm >> 1) & 0x3FF) << 21)
        | (((imm >> 11) & 1) << 20)
        | (((imm >> 12) & 0xFF) << 12)
        | (rd << 7)
        | _OP_JAL
    )


def _run_words(words, **kwargs):
    iss = RV32ICIss(**kwargs)
    for index, word in enumerate(words):
        iss.poke_word(4 * index, word)
    iss.run(len(words))
    return iss


def test_iss_reset_state():
    iss = RV32ICIss(reset_vector=0x100)
    assert iss.pc == 0x100
    assert iss.x == [0] * 32
    assert not iss.halted


def test_iss_alu_immediate():
    words = [
        _i(10, 0, 0, 1),  # addi x1, x0, 10
        _i(0x400 | 1, 1, 5, 2),  # srai x2, x1, 1 -> 5
        _i(1, 1, 1, 3),  # slli x3, x1, 1 -> 20
        _i(0xFFF, 0, 0, 4),  # addi x4, x0, -1
        _i(0, 4, 2, 5),  # slti x5, x4, 0 -> 1
        _i(0, 4, 3, 6),  # sltiu x6, x4(0xFFFFFFFF), 0 -> 0
        _i(0x0F0, 1, 7, 7),  # andi x7, x1, 0xF0 -> 0
        _i(0x0F0, 1, 6, 8),  # ori x8, x1, 0xF0 -> 0xFA
        _i(0x0FF, 1, 4, 9),  # xori x9, x1, 0xFF -> 0xF5
    ]
    iss = _run_words(words)
    assert (iss.x[1], iss.x[2], iss.x[3]) == (10, 5, 20)
    assert iss.x[4] == _MASK
    assert (iss.x[5], iss.x[6]) == (1, 0)
    assert (iss.x[7], iss.x[8], iss.x[9]) == (0, 0xFA, 0xF5)


def test_iss_alu_register():
    words = [
        _i(0x0FF, 0, 0, 1),  # addi x1, x0, 0xFF
        _i(3, 0, 0, 2),  # addi x2, x0, 3
        _r(0, 2, 1, 0, 3),  # add x3, x1, x2
        _r(0x20, 2, 1, 0, 4),  # sub x4, x1, x2
        _r(0, 2, 1, 1, 5),  # sll x5, x1, x2
        _r(0, 2, 1, 4, 6),  # xor x6, x1, x2
        _r(0, 2, 1, 6, 7),  # or x7, x1, x2
        _r(0, 2, 1, 7, 8),  # and x8, x1, x2
        _r(0, 2, 1, 2, 9),  # slt x9, x1, x2
        _r(0, 2, 1, 3, 10),  # sltu x10, x1, x2
    ]
    iss = _run_words(words)
    assert iss.x[3] == 0x102
    assert iss.x[4] == 0xFC
    assert iss.x[5] == 0x7F8
    assert iss.x[6] == 0xFC
    assert iss.x[7] == 0xFF
    assert iss.x[8] == 3
    assert iss.x[9] == 0
    assert iss.x[10] == 0


def test_iss_lui_auipc():
    words = [_u(0x12345000, 5, _OP_LUI), _u(0x1000, 6, _OP_AUIPC)]
    iss = _run_words(words)
    assert iss.x[5] == 0x12345000
    assert iss.x[6] == 0x1000 + 4  # pc of the second instruction


def test_iss_branches():
    words = [
        _i(0, 0, 0, 1),  # addi x1, x0, 0
        _i(1, 0, 0, 2),  # addi x2, x0, 1
        _b(8, 2, 1, 0),  # beq x1, x2, +8 (not taken)
        _i(0x111, 0, 0, 3),  # addi x3, x0, 0x111
        _b(8, 2, 2, 0),  # beq x2, x2, +8 (taken)
        _i(0x222, 0, 0, 4),  # addi x4, x0, 0x222 (skipped)
        _i(0x333, 0, 0, 5),  # addi x5, x0, 0x333
    ]
    iss = _run_words(words)
    assert iss.x[3] == 0x111
    assert iss.x[4] == 0
    assert iss.x[5] == 0x333


def test_iss_branch_signed_unsigned():
    words = [
        _i(0xFFF, 0, 0, 1),  # addi x1, x0, -1
        _i(1, 0, 0, 2),  # addi x2, x0, 1
        _b(8, 1, 2, 4),  # blt x2, x1, +8 -> 1 < -1? no
        _i(0x111, 0, 0, 3),
        _b(8, 1, 2, 6),  # bltu x2, x1, +8 -> 1 < 0xFFFFFFFF? yes
        _i(0x222, 0, 0, 4),
        _i(0x333, 0, 0, 5),
    ]
    iss = _run_words(words)
    assert iss.x[3] == 0x111
    assert iss.x[4] == 0
    assert iss.x[5] == 0x333


def test_iss_jal_and_jalr():
    words = [
        _j(8, 1),  # jal x1, +8 -> x1 = 4, pc = 8
        _i(0x111, 0, 0, 2),  # skipped
        _i(0x222, 0, 0, 3),  # at pc 8
        _i(0x18, 0, 0, 4),  # addi x4, x0, 0x18
        _i(0, 4, 0, 5, _OP_JALR),  # jalr x5, x4 -> x5 = 0x14, pc = 0x18
        _i(0x444, 0, 0, 6),  # skipped
        0x00100073,  # ebreak at 0x18
    ]
    iss = RV32ICIss()
    for index, word in enumerate(words):
        iss.poke_word(4 * index, word)
    iss.run()
    assert iss.x[1] == 4
    assert iss.x[3] == 0x222
    assert iss.x[6] == 0
    assert iss.x[5] == 0x14
    assert iss.halted and iss.cause == CAUSE["breakpoint"]


def test_iss_loads():
    words = [
        _i(0x100, 0, 0, 1),  # addi x1, x0, 0x100
        _i(0, 1, 2, 2, _OP_LOAD),  # lw x2, 0(x1)
        _i(0, 1, 1, 3, _OP_LOAD),  # lh x3, 0(x1)
        _i(0, 1, 5, 4, _OP_LOAD),  # lhu x4, 0(x1)
        _i(0, 1, 0, 5, _OP_LOAD),  # lb x5, 0(x1)
        _i(0, 1, 4, 6, _OP_LOAD),  # lbu x6, 0(x1)
        _i(3, 1, 0, 7, _OP_LOAD),  # lb x7, 3(x1)
    ]
    iss = RV32ICIss()
    iss.poke_word(0x100, 0x80FF7F01)
    for index, word in enumerate(words):
        iss.poke_word(4 * index, word)
    iss.run(len(words))
    assert iss.x[2] == 0x80FF7F01
    assert iss.x[3] == 0x7F01
    assert iss.x[4] == 0x7F01
    assert iss.x[5] == 1
    assert iss.x[6] == 1
    assert iss.x[7] == 0xFFFFFF80  # signed byte 0x80 at offset 3


def test_iss_stores():
    words = [
        _i(0x100, 0, 0, 1),  # addi x1, x0, 0x100
        _i(0x23, 0, 0, 2),  # addi x2, x0, 0x23
        _s(0, 2, 1, 2),  # sw x2, 0(x1)
        _s(4, 2, 1, 0),  # sb x2, 4(x1)
        _s(6, 2, 1, 1),  # sh x2, 6(x1)
        _i(0, 1, 2, 3, _OP_LOAD),  # lw x3, 0(x1)
    ]
    iss = _run_words(words)
    assert iss.x[3] == 0x23
    assert iss.peek_byte(0x104) == 0x23
    assert iss.peek_half(0x106) == 0x0023


def test_iss_compressed_matches_decompressed():
    words = [0x0001, 0x0285, 0x428D, 0x8316, 0xA011, 0x8082, 0x4505, 0xC001]
    for compressed in words:
        expanded, illegal = decompress(compressed)
        if illegal:
            continue
        c_iss = RV32ICIss()
        c_iss.poke_half(0, compressed)
        c_iss.run(1)
        w_iss = RV32ICIss()
        w_iss.poke_word(0, expanded)
        w_iss.run(1)
        # the 16-bit form advances the PC by 2, the expanded 32-bit form by 4,
        # so only the architectural register effect is comparable
        assert c_iss.x == w_iss.x, hex(compressed)


def test_iss_disabled_c_is_illegal():
    iss = RV32ICIss(with_c=False)
    iss.poke_half(0x0000, 0x0001)  # a 16-bit parcel
    iss.step()
    assert iss.halted
    assert iss.cause == CAUSE["illegal_instruction"]


def test_iss_illegal_instruction():
    iss = RV32ICIss()
    iss.poke_word(0, 0x00000000)
    iss.step()
    assert iss.cause == CAUSE["illegal_instruction"]


def test_iss_ecall_and_ebreak():
    ecall = RV32ICIss()
    ecall.poke_word(0, 0x00000073)
    ecall.step()
    assert ecall.cause == CAUSE["ecall"]
    ebreak = RV32ICIss()
    ebreak.poke_word(0, 0x00100073)
    ebreak.step()
    assert ebreak.cause == CAUSE["breakpoint"]


def test_iss_tohost_and_fromhost():
    iss = RV32ICIss(tohost=0x1000, fromhost=0x1004, fromhost_data=0xCAFE)
    iss.x[1] = 0x1004
    iss.poke_word(0, _i(0, 1, 2, 5, _OP_LOAD))  # lw x5, 0(x1)
    iss.step()
    assert iss.x[5] == 0xCAFE
    assert not iss.halted

    iss.pc = 0
    iss.x[1] = 0x1000
    iss.x[6] = 2 * 7 + 1
    iss.poke_word(0, _s(0, 6, 1, 2))  # sw x6, 0(x1)
    iss.step()
    assert iss.halted
    checker = SignatureChecker(tohost_addr=0x1000)
    checker.feed(iss.signature)
    assert checker.passed and checker.code == 7


def test_iss_region_faults():
    regions = [
        {"base": 0x00, "size": 0x10, "perms": "I", "access": "RO"},
        {"base": 0x10, "size": 0x10, "perms": "D", "access": "RW"},
        {"base": 0x20, "size": 0x10, "perms": "D", "access": "RO"},
    ]
    fetch = RV32ICIss(regions=regions)
    fetch.pc = 0x10
    fetch.step()
    assert fetch.cause == CAUSE["instruction_access"]

    load = RV32ICIss(regions=regions)
    load.x[1] = 0x00
    load.poke_word(0, _i(0, 1, 2, 5, _OP_LOAD))
    load.step()
    assert load.cause == CAUSE["load_access"]

    store = RV32ICIss(regions=regions)
    store.x[1] = 0x20
    store.poke_word(0, _s(0, 6, 1, 2))
    store.step()
    assert store.cause == CAUSE["store_access"]

    unmapped = RV32ICIss(regions=regions)
    unmapped.pc = 0x40
    unmapped.step()
    assert unmapped.cause == CAUSE["instruction_access"]


def test_iss_misaligned():
    fetch = RV32ICIss()
    fetch.pc = 0x2 + 1
    fetch.step()
    assert fetch.cause == CAUSE["instruction_misaligned"]

    load = RV32ICIss()
    load.x[1] = 0x2
    load.poke_word(0, _i(0, 1, 2, 5, _OP_LOAD))
    load.step()
    assert load.cause == CAUSE["load_misaligned"]

    store = RV32ICIss()
    store.x[1] = 0x1
    store.poke_word(0, _s(0, 6, 1, 1))
    store.step()
    assert store.cause == CAUSE["store_misaligned"]


def test_iss_retire_hook_and_load_image():
    image = MemoryImage([(0x00, _i(1, 0, 0, 5).to_bytes(4, "little"))])
    iss = RV32ICIss()
    iss.load_image(image)
    retire = iss.step()
    assert retire == Retire(0, _i(1, 0, 0, 5), 4)
    assert iss.x[5] == 1
    assert iss.pc == 4
    assert iss.retired == 1
    assert iss.state() == (4, tuple(iss.x))
