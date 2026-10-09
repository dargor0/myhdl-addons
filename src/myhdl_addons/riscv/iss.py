"""Plain-Python architectural RV32IC instruction-set simulator (``RC-FR-130``).

This is the **golden model** used for differential testing (Q22).  It is
*architectural* (no cycle timing) and simulation-only (``RC-CON-008``); it is
never converted to HDL.

State: ``pc``, ``x0``–``x31`` (``x0`` hard-wired to 0), the ``halted`` flag,
the halt ``cause``/``signature`` and the host ``fromhost`` input.  Legality and
faults follow the RTL exactly so differential runs never diverge on faults
(Q22):

* the C extension is decoded with the shared :func:`~myhdl_addons.riscv.rvc.decompress`
  (so disabled/illegal 16-bit encodings match the RTL);
* a fetch from an unmapped/non-``I`` region, a load/store from a non-``D``
  region, a store to an ``RO`` region, and misaligned fetch/data addresses halt
  with the RISC-V cause code;
* stores to ``tohost`` latch the signature and halt, loads from ``fromhost``
  return the host input — both exempt from access faults (``RC-FR-111``).

The region map mirrors :class:`~myhdl_addons.riscv.router.MemoryRouter`
(``base``/``size``/``perms``/``access``); omitting it gives a flat, fully
mapped memory.
"""

from dataclasses import dataclass

from .rvc import decompress

__all__ = ["CAUSE", "Retire", "RV32ICIss"]

#: RISC-V exception cause codes (machine mode).
CAUSE = {
    "instruction_misaligned": 0,
    "instruction_access": 1,
    "illegal_instruction": 2,
    "breakpoint": 3,
    "load_misaligned": 4,
    "load_access": 5,
    "store_misaligned": 6,
    "store_access": 7,
    "ecall": 11,
}

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
_OP_MISC = 0x0F
_OP_SYSTEM = 0x73


def _sext(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _imm_i(instr: int) -> int:
    return _sext((instr >> 20) & 0xFFF, 12)


def _imm_s(instr: int) -> int:
    return _sext(((instr >> 25) << 5) | ((instr >> 7) & 0x1F), 12)


def _imm_b(instr: int) -> int:
    imm = (
        (((instr >> 31) & 1) << 12)
        | (((instr >> 7) & 1) << 11)
        | (((instr >> 25) & 0x3F) << 5)
        | (((instr >> 8) & 0xF) << 1)
    )
    return _sext(imm, 13)


def _imm_u(instr: int) -> int:
    return instr & 0xFFFFF000


def _imm_j(instr: int) -> int:
    imm = (
        (((instr >> 31) & 1) << 20)
        | (((instr >> 12) & 0xFF) << 12)
        | (((instr >> 20) & 1) << 11)
        | (((instr >> 21) & 0x3FF) << 1)
    )
    return _sext(imm, 21)


@dataclass(frozen=True)
class Retire:
    """One retired instruction (the differential retire hook, Q22)."""

    pc: int
    instr: int
    length: int


def _normalize(regions) -> tuple[dict, ...]:
    out = []
    for region in regions:
        out.append(
            {
                "base": int(region["base"]),
                "size": int(region["size"]),
                "perms": str(region.get("perms", "ID")).upper(),
                "access": str(region.get("access", "RW")).upper(),
            }
        )
    return tuple(out)


class RV32ICIss:
    """Architectural RV32I + C simulator."""

    def __init__(
        self,
        regions=None,
        tohost: int | None = None,
        fromhost: int | None = None,
        reset_vector: int = 0,
        with_c: bool = True,
        fromhost_data: int = 0,
    ) -> None:
        self.regions = _normalize(regions) if regions else None
        self.tohost = tohost
        self.fromhost = fromhost
        self.with_c = with_c
        self.fromhost_data = fromhost_data & _MASK
        self.reset_vector = reset_vector & _MASK
        self.x = [0] * 32
        self.pc = self.reset_vector
        self.halted = False
        self.cause: int | None = None
        self.signature = 0
        self.retired = 0
        self.last_retire: Retire | None = None
        self._mem: dict[int, int] = {}

    # -- memory access (no region checks: test setup) ----------------------
    def poke_byte(self, addr: int, value: int) -> None:
        self._mem[addr] = value & 0xFF

    def poke_half(self, addr: int, value: int) -> None:
        for lane in range(2):
            self.poke_byte(addr + lane, value >> (8 * lane))

    def poke_word(self, addr: int, value: int) -> None:
        for lane in range(4):
            self.poke_byte(addr + lane, value >> (8 * lane))

    def peek_byte(self, addr: int) -> int:
        return self._mem.get(addr, 0)

    def peek_half(self, addr: int) -> int:
        return self.peek_byte(addr) | (self.peek_byte(addr + 1) << 8)

    def peek_word(self, addr: int) -> int:
        value = 0
        for lane in range(4):
            value |= self.peek_byte(addr + lane) << (8 * lane)
        return value

    def load_image(self, image, base: int = 0, size=None) -> None:
        """Preload bytes from a :class:`MemoryImage` (segments or a region)."""
        if size is None:
            for seg_addr, data in image.segments:
                for offset, byte in enumerate(data):
                    self.poke_byte(seg_addr + offset, byte)
            return
        for index, word in enumerate(image.region_words(base, size)):
            self.poke_word(base + 4 * index, word)

    # -- region mapping ----------------------------------------------------
    def _find(self, addr: int):
        if self.regions is None:
            return {"base": 0, "size": 1 << 32, "perms": "ID", "access": "RW"}
        for region in self.regions:
            if region["base"] <= addr < region["base"] + region["size"]:
                return region
        return None

    def _spans_one_region(self, addr: int, size: int) -> bool:
        region = self._find(addr)
        if region is None:
            return False
        return addr + size - 1 < region["base"] + region["size"]

    # -- fault helpers -----------------------------------------------------
    def _fault(self, cause: int) -> None:
        self.halted = True
        self.cause = cause

    # -- fetch -------------------------------------------------------------
    def _fetch(self):
        """Return ``(word32, length)`` or ``None`` after halting."""
        if self.pc & 1:
            self._fault(CAUSE["instruction_misaligned"])
            return None
        region = self._find(self.pc)
        if region is None or "I" not in region["perms"]:
            self._fault(CAUSE["instruction_access"])
            return None
        parcel = self.peek_half(self.pc)
        if (parcel & 0x3) != 0x3:
            if not self.with_c:
                self._fault(CAUSE["illegal_instruction"])
                return None
            word, illegal = decompress(parcel)
            if illegal:
                self._fault(CAUSE["illegal_instruction"])
                return None
            return word, 2
        second = self._find(self.pc + 2)
        if second is None or "I" not in second["perms"]:
            self._fault(CAUSE["instruction_access"])
            return None
        return parcel | (self.peek_half(self.pc + 2) << 16), 4

    # -- load/store --------------------------------------------------------
    def _load(self, addr: int, size: int, signed: bool):
        nbytes = 1 << size
        if (size == 2 and (addr & 0x3)) or (size == 1 and (addr & 0x1)):
            self._fault(CAUSE["load_misaligned"])
            return None
        if addr == self.fromhost:
            value = self.fromhost_data
        else:
            region = self._find(addr)
            if (
                region is None
                or "D" not in region["perms"]
                or not self._spans_one_region(addr, nbytes)
            ):
                self._fault(CAUSE["load_access"])
                return None
            value = 0
            for lane in range(nbytes):
                value |= self.peek_byte(addr + lane) << (8 * lane)
        if signed:
            value = _sext(value, 8 * nbytes)
        return value & _MASK

    def _store(self, addr: int, size: int, value: int) -> None:
        nbytes = 1 << size
        if (size == 2 and (addr & 0x3)) or (size == 1 and (addr & 0x1)):
            self._fault(CAUSE["store_misaligned"])
            return
        if addr == self.tohost:
            self.signature = value & _MASK
            self.halted = True
            return
        region = self._find(addr)
        if (
            region is None
            or "D" not in region["perms"]
            or region["access"] != "RW"
            or not self._spans_one_region(addr, nbytes)
        ):
            self._fault(CAUSE["store_access"])
            return
        for lane in range(nbytes):
            self.poke_byte(addr + lane, value >> (8 * lane))

    # -- execution ---------------------------------------------------------
    def step(self):
        """Execute one instruction; return its :class:`Retire` or ``None``."""
        if self.halted:
            return None
        pc = self.pc
        fetched = self._fetch()
        if fetched is None:
            return None
        instr, length = fetched
        retire = Retire(pc, instr, length)
        self._execute(instr, length)
        self.last_retire = retire
        self.retired += 1
        return retire

    def run(self, max_steps: int = 100000):
        """Run until halt or *max_steps*; return the number of steps executed."""
        steps = 0
        while not self.halted and steps < max_steps:
            if self.step() is None:
                break
            steps += 1
        return steps

    def state(self):
        """Return ``(pc, tuple(x))`` for differential comparison."""
        return self.pc, tuple(self.x)

    # -- instruction implementation ---------------------------------------
    def _write(self, rd: int, value: int) -> None:
        if rd != 0:
            self.x[rd] = value & _MASK

    def _execute(self, instr: int, length: int) -> None:
        opcode = instr & 0x7F
        rd = (instr >> 7) & 0x1F
        rs1 = (instr >> 15) & 0x1F
        rs2 = (instr >> 20) & 0x1F
        funct3 = (instr >> 12) & 0x7
        funct7 = (instr >> 25) & 0x7F
        a = self.x[rs1]
        b = self.x[rs2]

        if opcode == _OP_LUI:
            self._write(rd, _imm_u(instr))
            self.pc = (self.pc + length) & _MASK
        elif opcode == _OP_AUIPC:
            self._write(rd, (self.pc + _imm_u(instr)) & _MASK)
            self.pc = (self.pc + length) & _MASK
        elif opcode == _OP_JAL:
            self._write(rd, (self.pc + length) & _MASK)
            self.pc = (self.pc + _imm_j(instr)) & _MASK
        elif opcode == _OP_JALR:
            if funct3 != 0:
                self._fault(CAUSE["illegal_instruction"])
                return
            target = (a + _imm_i(instr)) & _MASK
            self._write(rd, (self.pc + length) & _MASK)
            self.pc = target & ~1
        elif opcode == _OP_BRANCH:
            self._branch(funct3, a, b, instr, length)
        elif opcode == _OP_LOAD:
            self._execute_load(funct3, rd, a, instr, length)
        elif opcode == _OP_STORE:
            self._execute_store(funct3, a, b, instr, length)
        elif opcode == _OP_IMM:
            self._execute_imm(funct3, funct7, rd, a, instr, length)
        elif opcode == _OP:
            self._execute_op(funct3, funct7, rd, a, b, length)
        elif opcode == _OP_MISC:
            self.pc = (self.pc + length) & _MASK  # FENCE / FENCE.I: no-op
        elif opcode == _OP_SYSTEM:
            self._execute_system(instr, funct3, length)
        else:
            self._fault(CAUSE["illegal_instruction"])

    def _branch(self, funct3, a, b, instr, length) -> None:
        sa = _sext(a, 32)
        sb = _sext(b, 32)
        if funct3 == 0:
            taken = a == b
        elif funct3 == 1:
            taken = a != b
        elif funct3 == 4:
            taken = sa < sb
        elif funct3 == 5:
            taken = sa >= sb
        elif funct3 == 6:
            taken = a < b
        elif funct3 == 7:
            taken = a >= b
        else:
            self._fault(CAUSE["illegal_instruction"])
            return
        if taken:
            self.pc = (self.pc + _imm_b(instr)) & _MASK
        else:
            self.pc = (self.pc + length) & _MASK

    def _execute_load(self, funct3, rd, base, instr, length) -> None:
        sizes = {0: (0, True), 1: (1, True), 2: (2, True), 4: (0, False), 5: (1, False)}
        if funct3 not in sizes:
            self._fault(CAUSE["illegal_instruction"])
            return
        size, signed = sizes[funct3]
        value = self._load((base + _imm_i(instr)) & _MASK, size, signed)
        if value is None:
            return
        self._write(rd, value)
        self.pc = (self.pc + length) & _MASK

    def _execute_store(self, funct3, base, value, instr, length) -> None:
        sizes = {0: 0, 1: 1, 2: 2}
        if funct3 not in sizes:
            self._fault(CAUSE["illegal_instruction"])
            return
        self._store((base + _imm_s(instr)) & _MASK, sizes[funct3], value)
        if not self.halted:
            self.pc = (self.pc + length) & _MASK

    def _execute_imm(self, funct3, funct7, rd, a, instr, length) -> None:
        imm = _imm_i(instr)
        shamt = imm & 0x1F
        if funct3 == 0:
            result = a + imm
        elif funct3 == 2:
            result = int(_sext(a, 32) < imm)
        elif funct3 == 3:
            result = int(a < (imm & _MASK))
        elif funct3 == 4:
            result = a ^ imm
        elif funct3 == 6:
            result = a | imm
        elif funct3 == 7:
            result = a & imm
        elif funct3 == 1:
            if funct7 != 0:
                self._fault(CAUSE["illegal_instruction"])
                return
            result = a << shamt
        elif funct3 == 5:
            if funct7 == 0:
                result = a >> shamt
            elif funct7 == 0x20:
                result = _sext(a, 32) >> shamt
            else:
                self._fault(CAUSE["illegal_instruction"])
                return
        else:
            self._fault(CAUSE["illegal_instruction"])
            return
        self._write(rd, result)
        self.pc = (self.pc + length) & _MASK

    def _execute_op(self, funct3, funct7, rd, a, b, length) -> None:
        if funct7 == 0x00:
            table = {
                0: a + b,
                1: a << (b & 0x1F),
                2: int(_sext(a, 32) < _sext(b, 32)),
                3: int(a < b),
                4: a ^ b,
                5: a >> (b & 0x1F),
                6: a | b,
                7: a & b,
            }
        elif funct7 == 0x20:
            table = {
                0: a - b,
                5: _sext(a, 32) >> (b & 0x1F),
            }
        else:
            self._fault(CAUSE["illegal_instruction"])
            return
        if funct3 not in table:
            self._fault(CAUSE["illegal_instruction"])
            return
        self._write(rd, table[funct3])
        self.pc = (self.pc + length) & _MASK

    def _execute_system(self, instr, funct3, length) -> None:
        # CSR / privileged ops are not in M1; only exact ECALL/EBREAK are legal.
        if instr == 0x00000073:
            self._fault(CAUSE["ecall"])
        elif instr == 0x00100073:
            self._fault(CAUSE["breakpoint"])
        else:
            self._fault(CAUSE["illegal_instruction"])
