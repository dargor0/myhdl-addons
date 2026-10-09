"""Simulation-only testbench helpers (``RC-FR-120..124``).

These helpers back the core testbenches and are **never converted** to HDL
(``RC-FR-124``); they are plain Python.

* :class:`MemoryImage` — a little-endian program image loaded from a minimal
  **ELF32** (``ET_EXEC``/``PT_LOAD`` at ``p_paddr``) or a word-addressed
  ``.hex`` file (``RC-FR-120/121``, Q21).  :meth:`MemoryImage.region_words`
  extracts a region's word tuple, so one image feeds every internal region.
* :class:`MemoryBfm` — a sparse byte-addressed simulation memory model (the
  "memory BFM", ``RC-FR-120``) with word/half/byte access and a write log; it
  can be preloaded from a :class:`MemoryImage` and backs external bus regions.
* :func:`decode_signature` / :class:`SignatureChecker` — the ``tohost`` result
  convention (``bit0 = 1`` pass, otherwise the exit code is ``value >> 1``,
  ``RC-FR-112/122``) read from a BFM write log or a value.
* :func:`contents_from_config` — resolve a :class:`CoreConfig`'s ``init`` files
  into ``{region_name: words}`` for :class:`MemoryRouter` (``RC-FR-109``).
"""

import struct
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MemoryBfm",
    "MemoryImage",
    "Signature",
    "SignatureChecker",
    "contents_from_config",
    "decode_signature",
    "elf_symbols",
]

_ELF_MAGIC = b"\x7fELF"
_ELFCLASS32 = 1
_ELFDATA2LSB = 1
_EM_RISCV = 0xF3
_ET_EXEC = 2
_PT_LOAD = 1
_WORD = 4


@dataclass(frozen=True)
class Signature:
    """A decoded ``tohost`` result."""

    passed: bool
    code: int


def decode_signature(value: int) -> Signature:
    """Decode the standard ``tohost`` value (``RC-FR-112``).

    ``bit0 == 1`` means pass; the exit code is ``value >> 1``.
    """
    if value < 0:
        raise ValueError(f"signature must be non-negative, got {value}")
    return Signature(bool(value & 1), value >> 1)


class MemoryImage:
    """A little-endian program image (ELF32 or word-addressed ``.hex``)."""

    def __init__(self, segments=()):
        self.segments = tuple((int(addr), bytes(data)) for addr, data in segments)
        self.entry = 0

    @classmethod
    def from_hex(cls, path, base: int = 0) -> "MemoryImage":
        """Read a word-addressed ``.hex`` file (one 32-bit word per token)."""
        words = []
        for token in Path(path).read_text(encoding="ascii").split():
            if len(token) > 8:
                raise ValueError(f"hex word {token!r} is more than 32 bits")
            try:
                word = int(token, 16)
            except ValueError:
                raise ValueError(f"invalid hex word {token!r}") from None
            words.append(word)
        data = b"".join(word.to_bytes(_WORD, "little") for word in words)
        return cls([(base, data)])

    @classmethod
    def from_elf(cls, path) -> "MemoryImage":
        """Read a minimal ELF32 ``ET_EXEC`` image (``RC-FR-120``, Q21)."""
        data = Path(path).read_bytes()
        if len(data) < 52 or data[:4] != _ELF_MAGIC:
            raise ValueError("not an ELF image (bad magic)")
        if data[4] != _ELFCLASS32:
            raise ValueError("not an ELFCLASS32 image")
        if data[5] != _ELFDATA2LSB:
            raise ValueError("not a little-endian (ELFDATA2LSB) image")
        e_type, e_machine = struct.unpack_from("<HH", data, 16)
        if e_type != _ET_EXEC:
            raise ValueError(f"ELF e_type {e_type} is not ET_EXEC")
        if e_machine != _EM_RISCV:
            raise ValueError(f"ELF e_machine {e_machine:#x} is not RISC-V")
        e_phoff = struct.unpack_from("<I", data, 28)[0]
        e_phentsize, e_phnum = struct.unpack_from("<HH", data, 42)
        segments = []
        for index in range(e_phnum):
            offset = e_phoff + index * e_phentsize
            (
                p_type,
                p_offset,
                _p_vaddr,
                p_paddr,
                p_filesz,
                p_memsz,
                _p_flags,
                _p_align,
            ) = struct.unpack_from("<8I", data, offset)
            if p_type != _PT_LOAD or p_filesz == 0:
                continue
            chunk = data[p_offset : p_offset + p_filesz]
            if p_memsz > p_filesz:
                chunk = chunk + b"\x00" * (p_memsz - p_filesz)
            segments.append((p_paddr, chunk))
        image = cls(segments)
        image.entry = struct.unpack_from("<I", data, 24)[0]
        return image

    @classmethod
    def load(cls, path, base: int = 0) -> "MemoryImage":
        """Load *path*, detecting ELF by magic and otherwise treating it as hex."""
        with Path(path).open("rb") as handle:
            magic = handle.read(4)
        if magic == _ELF_MAGIC:
            return cls.from_elf(path)
        return cls.from_hex(path, base=base)

    def region_words(self, base: int, size: int) -> tuple[int, ...]:
        """Return the little-endian words of *base*/*size* from the image."""
        depth = size // _WORD
        words = [0] * depth
        for seg_addr, data in self.segments:
            for offset, byte in enumerate(data):
                addr = seg_addr + offset
                if base <= addr < base + size:
                    index = (addr - base) // _WORD
                    shift = 8 * ((addr - base) % _WORD)
                    words[index] |= byte << shift
        return tuple(words)


def elf_symbols(path) -> dict[str, int]:
    """Return ``{name: value}`` from an ELF32 ``.symtab`` section."""
    data = Path(path).read_bytes()
    if len(data) < 52 or data[:4] != _ELF_MAGIC:
        raise ValueError("not an ELF image (bad magic)")
    e_shoff = struct.unpack_from("<I", data, 32)[0]
    e_shentsize, e_shnum, _e_shstrndx = struct.unpack_from("<HHH", data, 46)
    sections = [
        struct.unpack_from("<10I", data, e_shoff + i * e_shentsize)
        for i in range(e_shnum)
    ]
    symbols: dict[str, int] = {}
    for section in sections:
        if section[1] != 2:  # SHT_SYMTAB
            continue
        stroff = sections[section[6]][4]
        entsize = section[9] or 16
        for index in range(section[5] // entsize):
            offset = section[4] + index * entsize
            st_name, st_value, _size, _info, _other, _shndx = struct.unpack_from(
                "<IIIBBH", data, offset
            )
            if st_name == 0:
                continue
            end = data.index(b"\x00", stroff + st_name)
            name = data[stroff + st_name : end].decode("ascii", "replace")
            symbols[name] = st_value
    return symbols


class MemoryBfm:
    """A sparse, byte-addressed simulation memory (the memory BFM)."""

    def __init__(self):
        self._bytes: dict[int, int] = {}
        self.writes: list[tuple[int, int, int]] = []

    def write_byte(self, addr: int, value: int) -> None:
        self._bytes[addr] = value & 0xFF
        self.writes.append((addr, value & 0xFF, 0))

    def write_half(self, addr: int, value: int) -> None:
        for lane in range(2):
            self._bytes[addr + lane] = (value >> (8 * lane)) & 0xFF
        self.writes.append((addr, value & 0xFFFF, 1))

    def write_word(self, addr: int, value: int) -> None:
        for lane in range(_WORD):
            self._bytes[addr + lane] = (value >> (8 * lane)) & 0xFF
        self.writes.append((addr, value & 0xFFFFFFFF, 2))

    def read_byte(self, addr: int) -> int:
        return self._bytes.get(addr, 0)

    def read_half(self, addr: int) -> int:
        return self.read_byte(addr) | (self.read_byte(addr + 1) << 8)

    def read_word(self, addr: int) -> int:
        value = 0
        for lane in range(_WORD):
            value |= self.read_byte(addr + lane) << (8 * lane)
        return value

    def load_image(self, image: MemoryImage, base: int = 0, size=None) -> None:
        """Preload from *image*: a whole region (``base``/``size``) or segments."""
        if size is None:
            for seg_addr, data in image.segments:
                for offset, byte in enumerate(data):
                    self._bytes[seg_addr + offset] = byte
            return
        words = image.region_words(base, size)
        for index, word in enumerate(words):
            self.write_word(base + _WORD * index, word)


class SignatureChecker:
    """Reads a test's result from its ``tohost`` write (``RC-FR-122``)."""

    def __init__(self, tohost_addr: int = 0x1000):
        self.tohost_addr = tohost_addr
        self.value: int | None = None

    def feed(self, value: int) -> None:
        """Record a ``tohost`` value directly."""
        self.value = int(value)

    def observe(self, bfm: MemoryBfm):
        """Scan a BFM's write log for the last write to ``tohost``."""
        for addr, value, _size in bfm.writes:
            if addr == self.tohost_addr:
                self.value = value
        return self.result()

    @property
    def resolved(self) -> bool:
        return self.value is not None

    def result(self) -> Signature:
        """Return the decoded signature, raising if no ``tohost`` write happened."""
        if self.value is None:
            raise ValueError("no tohost write observed")
        return decode_signature(self.value)

    @property
    def passed(self) -> bool:
        return self.result().passed

    @property
    def code(self) -> int:
        return self.result().code


def contents_from_config(cfg) -> dict[str, tuple[int, ...]]:
    """Resolve a ``CoreConfig``'s internal ``init`` images into word tuples."""
    contents: dict[str, tuple[int, ...]] = {}
    for region in cfg.regions:
        if region["target"] != "internal" or region["init"] is None:
            continue
        path = Path(region["init"])
        if not path.is_absolute():
            path = Path(cfg.config_dir) / path
        image = MemoryImage.load(str(path), base=region["base"])
        contents[region["name"]] = image.region_words(region["base"], region["size"])
    return contents
