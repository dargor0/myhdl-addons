"""RISC-V ``CoreConfig`` and derived properties (``RC-FR-001..014``)."""

from pathlib import Path

import pytest

from myhdl_addons.common import (
    BusConfigError,
    BusError,
    BusTypeError,
    HdlConfigError,
    HdlError,
)
from myhdl_addons.common import (
    RiscvConfigError as CommonRiscvConfigError,
)
from myhdl_addons.common import (
    RiscvError as CommonRiscvError,
)
from myhdl_addons.riscv import (
    AVAIL_ACCESS,
    AVAIL_BASES,
    AVAIL_BUS_TYPES,
    AVAIL_EXTENSIONS,
    AVAIL_FETCH_BUFFER,
    AVAIL_PERMS,
    AVAIL_PIPELINE_STAGES,
    MISA_BITS,
    CoreConfig,
    RiscvConfigError,
    RiscvError,
    RiscvTypeError,
)
from myhdl_addons.riscv.errors import RiscvTypeError as RiscvTypeFromErrors

_CONFIG = Path(__file__).resolve().parents[1] / "config"
_EXAMPLE = _CONFIG / "riscv_example.ini"
_MINIMAL = _CONFIG / "riscv_minimal.ini"


def _core(**over):
    core = {
        "name": "mcu0",
        "reset_vector": "0x0",
        "tohost": "0x1000",
        "fromhost": "0x1004",
    }
    core.update(over)
    return core


def _region(**over):
    region = {
        "base": "0x0",
        "size": "0x10000",
        "perms": "ID",
        "access": "RW",
        "target": "internal",
    }
    region.update(over)
    return region


def _mapping(**over):
    data = {"core": _core(), "region.ram": _region()}
    data.update(over)
    return data


def test_example_files_exist():
    assert _EXAMPLE.is_file()
    assert _MINIMAL.is_file()


def test_from_ini_example():
    cfg = CoreConfig.from_ini(_EXAMPLE)
    assert cfg.get("core", "name") == "mcu0"
    assert cfg.isa_string == "rv32ic"
    assert cfg.misa == 0x40000104
    assert cfg.extensions == ("c",)
    assert set(cfg.buses) == {"mem", "periph"}
    assert cfg.buses["periph"]["type"] == "axi"
    assert len(cfg.regions) == 4
    assert cfg.regions[0]["target"] == "internal"
    assert cfg.regions[0]["init_format"] == "hex"
    assert cfg.regions[2]["target"] == "bus:mem"


def test_from_ini_minimal():
    cfg = CoreConfig.from_ini(_MINIMAL)
    assert cfg.get("core", "name") == "tiny"
    assert cfg.isa_string == "rv32ic"
    assert cfg.buses == {}
    assert len(cfg.regions) == 1


def test_configparser_interface_is_kept():
    cfg = CoreConfig.from_ini(_MINIMAL)
    assert "region.ram" in cfg.sections()
    assert cfg.getint("region.ram", "base") == 0x0
    assert cfg.getint("region.ram", "size") == 0x10000
    assert cfg.get("core", "name") == "tiny"
    assert cfg.getboolean("core", "interrupts", fallback=False) is False


def test_from_mapping_programmatic():
    cfg = CoreConfig.from_mapping(
        {
            "core": {"reset_vector": 0x0, "tohost": 0x1000, "fromhost": 0x1004},
            "region.ram": {
                "base": 0x0,
                "size": 0x10000,
                "perms": "ID",
                "access": "RW",
                "target": "internal",
            },
        }
    )
    assert cfg.get("core", "name") == "mcu0"
    assert cfg.get("pipeline", "stages") == "3"  # defaults materialised
    assert cfg.getint("pipeline", "stages") == 3
    assert cfg.xlen == 32  # derived from base
    assert cfg.isa_string == "rv32ic"
    assert cfg.misa == 0x40000104
    assert cfg.extensions == ("c",)
    assert cfg.buses == {}
    assert cfg.regions[0]["name"] == "ram"


def test_internal_region_init_options(tmp_path):
    elf = tmp_path / "blob.elf"
    elf.write_bytes(b"\x7fELF")
    cfg = CoreConfig.from_mapping(
        _mapping(
            **{
                "region.ram": _region(
                    init=str(elf), init_format="ELF", init_fit="truncate"
                )
            }
        )
    )
    region = cfg.regions[0]
    assert region["init"] == str(elf)
    assert region["init_format"] == "elf"  # lowercased
    assert region["init_fit"] == "truncate"


def test_init_fit_defaults_to_strict(tmp_path):
    hexfile = tmp_path / "fw.hex"
    hexfile.write_text("00000013\n", encoding="ascii")
    cfg = CoreConfig.from_mapping(
        _mapping(**{"region.ram": _region(init=str(hexfile), init_format="hex")})
    )
    assert cfg.regions[0]["init_fit"] == "strict"


def test_raw_init_size_checked(tmp_path):
    raw = tmp_path / "fw.bin"
    raw.write_bytes(b"\x00" * 16)
    strict = _mapping(
        **{"region.ram": _region(size="0x10", init=str(raw), init_format="raw")}
    )
    CoreConfig.from_mapping(strict)  # 16 bytes == region size
    raw.write_bytes(b"\x00" * 8)
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_mapping(strict)  # strict: 8 != 16
    truncate = _mapping(
        **{
            "region.ram": _region(
                size="0x10", init=str(raw), init_format="raw", init_fit="truncate"
            )
        }
    )
    assert CoreConfig.from_mapping(truncate).regions[0]["init_fit"] == "truncate"


def test_elf_bad_magic_raises(tmp_path):
    bad = tmp_path / "fw.elf"
    bad.write_bytes(b"NOPE")
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_mapping(
            _mapping(**{"region.ram": _region(init=str(bad), init_format="elf")})
        )


def test_hex_bad_content_raises(tmp_path):
    bad = tmp_path / "fw.hex"
    bad.write_text("hello world\n", encoding="ascii")
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_mapping(
            _mapping(**{"region.ram": _region(init=str(bad), init_format="hex")})
        )


def test_missing_init_file_raises(tmp_path):
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_mapping(
            _mapping(
                **{
                    "region.ram": _region(
                        init=str(tmp_path / "nope.hex"), init_format="hex"
                    )
                }
            )
        )


def test_xlen_is_derived_from_base():
    assert CoreConfig.from_mapping(_mapping()).xlen == 32


def test_requires_at_least_one_region():
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_mapping({"core": _core()})


def test_c_disabled_is_plain_rv32i():
    cfg = CoreConfig.from_mapping(_mapping(**{"extension.c": {"enabled": "false"}}))
    assert cfg.extensions == ()
    assert cfg.isa_string == "rv32i"
    assert cfg.misa == 0x40000100


def test_buses_and_targets():
    cfg = CoreConfig.from_mapping(
        _mapping(
            **{
                "bus.mem": {"type": "wishbone"},
                "bus.periph": {"type": "axi", "addr_width": "32"},
                "region.dram": _region(
                    base="0x40000000", size="0x10000000", target="bus:mem"
                ),
                "region.periph": _region(
                    base="0x80000000",
                    size="0x100000",
                    perms="D",
                    target="bus:periph",
                ),
            }
        )
    )
    assert cfg.buses["mem"]["type"] == "wishbone"
    assert cfg.buses["periph"]["type"] == "axi"
    assert cfg.regions[1]["target"] == "bus:mem"


def test_tohost_fromhost_may_be_unmapped():
    cfg = CoreConfig.from_mapping(
        {
            "core": {
                "reset_vector": "0x0",
                "tohost": "0x1000",
                "fromhost": "0x1004",
            },
            "region.rom": _region(size="0x1000", perms="I", access="RO"),
        }
    )
    assert cfg.regions[0]["perms"] == "I"
    assert cfg.getint("core", "tohost") == 0x1000


def test_tohost_in_read_only_region_is_allowed():
    cfg = CoreConfig.from_mapping(_mapping(**{"region.ram": _region(access="RO")}))
    assert cfg.regions[0]["access"] == "RO"


def test_validate_is_idempotent():
    cfg = CoreConfig()
    cfg.read_dict(_mapping())
    assert cfg.validate() is None
    assert cfg.validate() is None


def test_as_dict_and_repr():
    cfg = CoreConfig.from_mapping(_mapping())
    info = cfg.as_dict()
    assert info["region.ram"]["base"] == "0x0"
    assert info["isa_string"] == "rv32ic"
    assert "misa" in info
    assert "CoreConfig" in repr(cfg)


@pytest.mark.parametrize(
    "over",
    [
        {"core": _core(reset_vector="zzz")},
        {"core": _core(tohost="2")},
        {"core": _core(bogus="1")},
        {"isa": {"base": "rv32e"}},
        {"isa": {"base": "rv32i", "isa": "rv32ic"}},  # ISA string is output-only
        {"pipeline": {"stages": "4"}},
        {"pipeline": {"fetch_buffer": "3"}},
        {"debug": {"trace": "maybe"}},
        {"region.ram": _region(size="0x3000")},
        {"region.ram": _region(base="0x100")},
        {"region.ram": _region(size="2")},
        {"region.ram": _region(perms="X")},
        {"region.ram": _region(access="WO")},
        {"region.ram": _region(perms="D")},  # reset not in an I region
        {"region.ram": _region(target="bus:missing")},
        {"region.ram": _region(init="fw.hex")},  # init requires init_format
        {"region.ram": _region(init_format="hex")},  # init_format requires init
        {"region.ram": _region(init="fw.hex", init_format="bin")},  # bad format
        {
            "region.ram": _region(init="fw.hex", init_format="hex", init_fit="clip")
        },  # bad fit
        {"region.ram": {"size": "0x10000"}},  # missing base
        {"region.ram": {"base": "0x0"}},  # missing size
        {"region.other": _region(base="0x8000", size="0x8000")},  # overlaps ram
        {"bus.mem": {"type": "usb"}},
        {"bus.mem": {"type": "wishbone", "bogus": "1"}},
        {"bogus": {"x": "1"}},
        {"extension.m": {"enabled": "true"}},
        {
            "bus.mem": {"type": "wishbone"},
            "region.ram": _region(target="bus:mem", init="x.hex"),
        },
    ],
)
def test_invalid_configuration_raises(over):
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_mapping(_mapping(**over))


def test_error_hierarchy():
    assert issubclass(RiscvError, BusError)
    assert issubclass(RiscvError, HdlError)
    assert issubclass(RiscvConfigError, RiscvError)
    assert issubclass(RiscvConfigError, BusConfigError)
    assert issubclass(RiscvConfigError, HdlConfigError)
    assert issubclass(RiscvTypeError, BusTypeError)
    err = RiscvConfigError("boom")
    assert isinstance(err, (HdlError, HdlConfigError, BusError, BusConfigError))
    assert isinstance(err, RiscvError)


def test_error_aliases_are_shared():
    assert RiscvConfigError is CommonRiscvConfigError
    assert RiscvError is CommonRiscvError
    assert RiscvTypeFromErrors is RiscvTypeError


def test_available_constants():
    assert AVAIL_BASES == ("rv32i",)
    assert AVAIL_EXTENSIONS == ("c",)
    assert AVAIL_PIPELINE_STAGES == (1, 2, 3)
    assert AVAIL_FETCH_BUFFER == (0, 1, 2)
    assert AVAIL_BUS_TYPES == ("wishbone", "axi")
    assert AVAIL_PERMS == ("I", "D", "ID")
    assert AVAIL_ACCESS == ("RO", "RW")
    assert set(MISA_BITS) == set(AVAIL_EXTENSIONS)


@pytest.mark.parametrize(
    "text",
    [
        "[bogus]\nx = 1\n[region.ram]\nbase=0x0\nsize=0x10000\n",
        "[core]\nbogus = 1\n[region.ram]\nbase=0x0\nsize=0x10000\n",
        "[core]\nreset_vector = zzz\n[region.ram]\nbase=0x0\nsize=0x10000\n",
        "[debug]\ntrace = maybe\n[region.ram]\nbase=0x0\nsize=0x10000\n",
        "[isa]\nbase = rv32i\nisa = rv32ic\n[region.ram]\nbase=0x0\nsize=0x10000\n",
    ],
)
def test_from_ini_errors(text, tmp_path):
    ini = tmp_path / "bad.ini"
    ini.write_text(text, encoding="utf-8")
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_ini(ini)


def test_from_ini_missing_file(tmp_path):
    with pytest.raises(RiscvConfigError):
        CoreConfig.from_ini(tmp_path / "nope.ini")
