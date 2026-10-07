"""``ImmGen`` immediate decoding and sign/zero extension (``RC-FR-022``)."""

from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.riscv import AVAIL_IMM_TYPES, ImmGen

_MASK = 0xFFFF_FFFF


def _sext(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _reference(word: int, kind: str) -> int:
    """Independent spec-level decoder (bits straight from the ISA manual)."""
    if kind == "I":
        return _sext((word >> 20) & 0xFFF, 12) & _MASK
    if kind == "S":
        value = (((word >> 25) & 0x7F) << 5) | ((word >> 7) & 0x1F)
        return _sext(value, 12) & _MASK
    if kind == "B":
        value = (
            (((word >> 31) & 1) << 12)
            | (((word >> 7) & 1) << 11)
            | (((word >> 25) & 0x3F) << 5)
            | (((word >> 8) & 0xF) << 1)
        )
        return _sext(value, 13) & _MASK
    if kind == "U":
        return (word >> 12) << 12
    if kind == "J":
        value = (
            (((word >> 31) & 1) << 20)
            | (((word >> 12) & 0xFF) << 12)
            | (((word >> 20) & 1) << 11)
            | (((word >> 21) & 0x3FF) << 1)
        )
        return _sext(value, 21) & _MASK
    raise ValueError(kind)


_WORDS = (
    0x00000000,
    0xFFFFFFFF,
    0x7FFFFFFF,
    0x80000000,
    0x00000013,  # addi x0, x0, 0
    0xFFF00093,  # addi x1, x0, -1
    0x7FF00093,  # addi x1, x0, 2047
    0x80000093,  # addi x1, x0, -2048
    0x00102023,  # sw x1, 0(x0)
    0xFE102FA3,  # sw x1, -1(x0)
    0x00000063,  # beq x0, x0, 0
    0x06300263,  # beq x0, x0, 100
    0x123450B7,  # lui x1, 0x12345
    0x008000EF,  # jal x1, 8
    0xFFDFF0EF,  # jal x1, -4
    0x00A00063,  # beqz-like branch word
)

_VECTORS = [(word, kind) for word in _WORDS for kind in AVAIL_IMM_TYPES]


@block
def _immgen_tb(results, vectors):
    comp = ImmGen()
    ports = comp.ports()
    dut = comp.hdl(ports)
    imm_map = comp.get_imm_intmap()

    @instance
    def stim():
        for word, kind in vectors:
            ports.instr.next = word
            ports.imm_sel.next = imm_map[kind]
            yield delay(1)
            results.append((kind, word, int(ports.imm)))
        raise StopSimulation

    return dut, stim


def _run(vectors):
    results = []
    _immgen_tb(results, vectors).run_sim()
    return results


def test_immgen_matches_reference():
    for kind, word, imm in _run(_VECTORS):
        assert imm == _reference(word, kind), f"{kind} {word:#010x}"


def test_known_immediates():
    cases = [
        (0xFFF00093, "I", 0xFFFFFFFF),  # addi x1, x0, -1
        (0x7FF00093, "I", 0x000007FF),  # addi x1, x0, 2047
        (0x80000093, "I", 0xFFFFF800),  # addi x1, x0, -2048
        (0x00102023, "S", 0x00000000),  # sw x1, 0(x0)
        (0xFE102FA3, "S", 0xFFFFFFFF),  # sw x1, -1(x0)
        (0x00000063, "B", 0x00000000),  # beq x0, x0, 0
        (0x06300263, "B", 0x00000064),  # beq x0, x0, 100
        (0x123450B7, "U", 0x12345000),  # lui x1, 0x12345
        (0x008000EF, "J", 0x00000008),  # jal x1, 8
        (0xFFDFF0EF, "J", 0xFFFFFFFC),  # jal x1, -4
    ]
    for word, kind, expected in cases:
        got = _run([(word, kind)])[0][2]
        assert got == expected, f"{kind} {word:#010x}: {got:#010x}"


@block
def _raw_sel_tb(results):
    comp = ImmGen()
    ports = comp.ports()
    dut = comp.hdl(ports)

    @instance
    def stim():
        ports.instr.next = 0xFFFFFFFF
        for code in range(1 << 3):
            ports.imm_sel.next = code
            yield delay(1)
            results.append((code, int(ports.imm)))
        raise StopSimulation

    return dut, stim


def test_unknown_selector_reads_zero():
    imm_map = ImmGen().get_imm_intmap()
    known = set(imm_map.values())
    assert len(known) == len(AVAIL_IMM_TYPES)  # 5 formats -> unassigned codes
    results = []
    _raw_sel_tb(results).run_sim()
    for code, imm in results:
        if code in known:
            expected = _reference(0xFFFFFFFF, AVAIL_IMM_TYPES[code])
            assert imm == expected
        else:
            assert imm == 0


def test_immgen_intmap_and_metadata():
    comp = ImmGen()
    imm_map = comp.get_imm_intmap()
    assert set(imm_map) == set(AVAIL_IMM_TYPES)
    assert len(set(imm_map.values())) == len(AVAIL_IMM_TYPES)
    assert comp.as_dict()["imm_types"] == AVAIL_IMM_TYPES
    assert "ImmGen" in repr(comp)
