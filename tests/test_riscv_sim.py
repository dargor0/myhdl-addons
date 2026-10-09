"""Simulation-only loader / memory-BFM / signature helpers (``RC-FR-120..124``).

Plain-Python (non-HDL) tests: ELF32 and ``.hex`` image loading, the sparse
memory BFM, and the ``tohost`` signature convention.
"""

import struct

import pytest

from myhdl_addons.riscv import (
    CoreConfig,
    MemoryBfm,
    MemoryImage,
    Signature,
    SignatureChecker,
    contents_from_config,
    decode_signature,
)


def _elf32(
    payload,
    paddr=0x1000,
    memsz=None,
    etype=2,
    machine=0xF3,
    elfclass=1,
    endian=1,
    magic=b"\x7fELF",
):
    """Build a one-segment little-endian ELF32 ``ET_EXEC`` image."""
    phoff = 52
    phentsize = 32
    offset = phoff + phentsize
    filesz = len(payload)
    if memsz is None:
        memsz = filesz
    ident = magic + bytes([elfclass, endian, 1, 0]) + b"\x00" * 8
    header = ident + struct.pack(
        "<HHIIIIIHHHHHH",
        etype,
        machine,
        1,
        paddr,
        phoff,
        0,
        0,
        52,
        phentsize,
        1,
        0,
        0,
        0,
    )
    phdr = struct.pack("<8I", 1, offset, paddr, paddr, filesz, memsz, 5, 4)
    return header + phdr + bytes(payload)


def test_decode_signature():
    assert decode_signature(1) == Signature(True, 0)
    assert decode_signature(0) == Signature(False, 0)
    assert decode_signature(2 * 7 + 1) == Signature(True, 7)
    assert decode_signature(2 * 3) == Signature(False, 3)
    with pytest.raises(ValueError):
        decode_signature(-1)


def test_memory_image_from_hex(tmp_path):
    path = tmp_path / "p.hex"
    path.write_text("00000013\n0000006f\n")
    image = MemoryImage.from_hex(str(path))
    assert image.region_words(0x00, 0x10) == (0x13, 0x6F, 0, 0)
    assert image.region_words(0x10, 0x10) == (0, 0, 0, 0)


def test_memory_image_hex_errors(tmp_path):
    too_wide = tmp_path / "wide.hex"
    too_wide.write_text("000000130\n")
    with pytest.raises(ValueError):
        MemoryImage.from_hex(str(too_wide))
    non_hex = tmp_path / "bad.hex"
    non_hex.write_text("nope\n")
    with pytest.raises(ValueError):
        MemoryImage.from_hex(str(non_hex))


def test_memory_image_from_elf(tmp_path):
    payload = bytes([0x13, 0x00, 0x00, 0x00, 0x6F, 0x00, 0x00, 0x00])
    path = tmp_path / "p.elf"
    path.write_bytes(_elf32(payload, paddr=0x1000))
    image = MemoryImage.from_elf(str(path))
    assert image.region_words(0x1000, 0x10) == (0x13, 0x6F, 0, 0)


def test_memory_image_elf_zero_fills_bss(tmp_path):
    path = tmp_path / "p.elf"
    path.write_bytes(_elf32(bytes([0x13, 0, 0, 0]), paddr=0, memsz=16))
    image = MemoryImage.from_elf(str(path))
    assert image.region_words(0x00, 0x10) == (0x13, 0, 0, 0)


@pytest.mark.parametrize("mutate", ["magic", "class", "endian", "machine", "etype"])
def test_memory_image_elf_rejects(mutate, tmp_path):
    kwargs = {}
    if mutate == "magic":
        kwargs["magic"] = b"XELF"
    elif mutate == "class":
        kwargs["elfclass"] = 2
    elif mutate == "endian":
        kwargs["endian"] = 2
    elif mutate == "machine":
        kwargs["machine"] = 0x03
    else:
        kwargs["etype"] = 1
    path = tmp_path / "p.elf"
    path.write_bytes(_elf32(bytes([0x13, 0, 0, 0]), **kwargs))
    with pytest.raises(ValueError):
        MemoryImage.from_elf(str(path))


def test_memory_image_load_autodetects(tmp_path):
    hex_path = tmp_path / "a.hex"
    hex_path.write_text("00000013\n")
    assert MemoryImage.load(str(hex_path)).region_words(0, 4) == (0x13,)
    elf_path = tmp_path / "a.elf"
    elf_path.write_bytes(_elf32(bytes([0x13, 0, 0, 0])))
    assert MemoryImage.load(str(elf_path)).region_words(0x1000, 4) == (0x13,)


def test_memory_bfm_read_write():
    bfm = MemoryBfm()
    bfm.write_word(0x10, 0xDEADBEEF)
    assert bfm.read_word(0x10) == 0xDEADBEEF
    assert bfm.read_byte(0x10) == 0xEF
    assert bfm.read_half(0x12) == 0xDEAD
    bfm.write_byte(0x11, 0x00)
    assert bfm.read_word(0x10) == 0xDEAD00EF
    bfm.write_half(0x12, 0x1234)
    assert bfm.read_word(0x10) == 0x123400EF
    assert bfm.read_word(0x1000) == 0
    assert bfm.writes[-1] == (0x12, 0x1234, 1)


def test_memory_bfm_load_image():
    bfm = MemoryBfm()
    bfm.load_image(MemoryImage([(0x00, bytes([0x13, 0, 0, 0, 0x6F, 0, 0, 0]))]))
    assert bfm.read_word(0x00) == 0x13
    assert bfm.read_word(0x04) == 0x6F
    region = MemoryBfm()
    region.load_image(
        MemoryImage([(0x100, bytes([1, 2, 3, 4]))]), base=0x100, size=0x10
    )
    assert region.read_word(0x100) == 0x04030201


def test_signature_checker_observe_and_feed():
    checker = SignatureChecker(tohost_addr=0x1000)
    assert not checker.resolved
    with pytest.raises(ValueError):
        checker.result()

    bfm = MemoryBfm()
    bfm.write_word(0x1000, 0)  # an unrelated early write
    bfm.write_word(0x1000, 2 * 5 + 1)
    assert checker.observe(bfm) == Signature(True, 5)
    assert checker.passed
    assert checker.code == 5

    direct = SignatureChecker(tohost_addr=0x1000)
    direct.feed(2 * 3)
    assert not direct.passed
    assert direct.code == 3


def test_contents_from_config(tmp_path):
    hex_path = tmp_path / "prog.hex"
    hex_path.write_text("00000013\n0000006f\n")
    cfg = CoreConfig.from_mapping(
        {
            "core": {
                "reset_vector": "0x0",
                "tohost": "0x1000",
                "fromhost": "0x1004",
            },
            "region.ram": {
                "base": "0x0",
                "size": "0x10",
                "perms": "ID",
                "access": "RW",
                "target": "internal",
                "init": str(hex_path),
                "init_format": "hex",
            },
        }
    )
    assert cfg.config_dir.exists()
    assert contents_from_config(cfg) == {"ram": (0x13, 0x6F, 0, 0)}
