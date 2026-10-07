"""RISC-V core configuration (``RC-FR-001..014``).

:class:`CoreConfig` is a single :class:`configparser.ConfigParser` subclass
that holds the configuration.  **Scalars** are read straight through the
standard interface (``get``/``getint``/``getboolean``); the **complex derived
data** that ``get*`` cannot express is exposed as properties — :attr:`regions`
(address map), :attr:`buses`, and the ISA views :attr:`extensions` /
:attr:`isa_string` / :attr:`misa`.  Boundary checks live in
:meth:`CoreConfig.validate`, called by :meth:`CoreConfig.from_ini` and
:meth:`CoreConfig.from_mapping`.

Loading an INI (``RC-FR-003``) or a mapping (``RC-FR-005``) validates the
result; invalid input raises
:class:`~myhdl_addons.common.errors.RiscvConfigError` (``RC-FR-007``).
"""

import configparser
import itertools
import string
from collections.abc import Mapping
from pathlib import Path

from ..common.config import (
    check_choice,
    check_non_negative,
    check_positive,
    check_power_of_two,
)
from ..common.errors import RiscvConfigError

__all__ = [
    "AVAIL_ACCESS",
    "AVAIL_BASES",
    "AVAIL_BUS_TYPES",
    "AVAIL_EXTENSIONS",
    "AVAIL_FETCH_BUFFER",
    "AVAIL_INIT_FIT",
    "AVAIL_INIT_FORMATS",
    "AVAIL_PERMS",
    "AVAIL_PIPELINE_STAGES",
    "MISA_BITS",
    "CoreConfig",
]

#: Supported base integer ISA (RV32E and alternate bases are out of scope).
AVAIL_BASES = ("rv32i",)

#: Supported ISA extensions (C is on by default; others are added later).
AVAIL_EXTENSIONS = ("c",)

#: Pipeline depths: ``1`` = non-pipelined bring-up, ``2``/``3`` pipelined.
AVAIL_PIPELINE_STAGES = (1, 2, 3)

#: Instruction-buffer depths in 16-bit parcels (``RC-FR-043``).
AVAIL_FETCH_BUFFER = (0, 1, 2)

#: Supported external-bus transports, selected per named bus.
AVAIL_BUS_TYPES = ("wishbone", "axi")

#: Region permissions: instruction, data, or both.
AVAIL_PERMS = ("I", "D", "ID")

#: Region access: read-only (writes fault) or read-write.
AVAIL_ACCESS = ("RO", "RW")

#: Supported preload image formats (``RC-FR-109``).
AVAIL_INIT_FORMATS = ("elf", "hex", "raw")

#: How an ``init`` image is fitted to its region (``RC-FR-109``).
AVAIL_INIT_FIT = ("strict", "truncate")

#: ``misa`` bit position contributed by each supported extension.
MISA_BITS = {"c": 2}

#: Register width implied by each supported base ISA (``RC-FR-034``).
_BASE_XLEN = {"rv32i": 32}

_MXL_32 = 1 << 30
_I_BIT = 1 << 8
_WORD = 4
_ADDR_SPACE = 1 << 32

_SECTION_KEYS = {
    "core": {"name", "reset_vector", "tohost", "fromhost", "interrupts"},
    "isa": {"base"},
    "registers": {"count"},
    "pipeline": {"stages", "fetch_buffer", "forwarding"},
    "debug": {"trace"},
}
_BUS_KEYS = {"type", "data_width", "addr_width"}
_REGION_KEYS = {
    "base",
    "size",
    "perms",
    "access",
    "target",
    "init",
    "init_format",
    "init_fit",
}
_EXTENSION_KEYS = {"enabled"}

#: Effective defaults materialised on load so ``get*`` returns real values.
_DEFAULT_OPTIONS = {
    "core": {
        "name": "mcu0",
        "reset_vector": "0x0",
        "tohost": "0x1000",
        "fromhost": "0x1004",
        "interrupts": "false",
    },
    "registers": {"count": "32"},
    "pipeline": {"stages": "3", "fetch_buffer": "1", "forwarding": "false"},
    "debug": {"trace": "false"},
}


def _check_name(value: object, what: str = "name") -> str:
    """Return *value* if it is a non-empty string, else raise."""
    if not isinstance(value, str) or not value:
        raise RiscvConfigError(f"{what} must be a non-empty string, got {value!r}")
    return value


def _check_width(value: object, name: str) -> int:
    """Return *value* if it is 32 (RV32), else raise."""
    width = check_positive(value, name, exc=RiscvConfigError)
    if width != 32:
        raise RiscvConfigError(f"{name} must be 32 for RV32, got {width!r}")
    return width


def _check_register_count(value: object) -> int:
    """Return *value* if it is the RV32I count ``32``, else raise."""
    count = check_positive(value, "register_count", exc=RiscvConfigError)
    if count != 32:
        raise RiscvConfigError(f"register_count must be 32 for RV32I, got {count!r}")
    return count


def _check_address(value: object, name: str) -> int:
    """Return *value* if it is a non-negative, word-aligned address."""
    address = check_non_negative(value, name, exc=RiscvConfigError)
    if address % _WORD != 0:
        raise RiscvConfigError(f"{name} must be 4-byte aligned, got {address:#x}")
    return address


def _check_size(value: object, name: str) -> int:
    """Return *value* if it is a power-of-two byte size of at least one word."""
    size = check_power_of_two(value, name, exc=RiscvConfigError)
    if size < _WORD:
        raise RiscvConfigError(f"{name} must be at least {_WORD} bytes, got {size}")
    return size


def _check_target(target: object, bus_map: Mapping[str, object], region: str) -> str:
    """Validate a region target: ``internal`` or ``bus:<declared name>``."""
    if target == "internal":
        return "internal"
    if isinstance(target, str) and target.startswith("bus:"):
        bus_name = target[4:]
        if bus_name not in bus_map:
            raise RiscvConfigError(
                f"region {region!r} targets undeclared bus {bus_name!r}"
            )
        return target
    raise RiscvConfigError(
        f"region {region!r}: target must be 'internal' or 'bus:<name>', got {target!r}"
    )


def _region_containing(region_map: tuple[dict, ...], address: int) -> dict | None:
    """Return the region containing *address*, or ``None``."""
    for region in region_map:
        if region["base"] <= address < region["base"] + region["size"]:
            return region
    return None


_HEX_DIGITS = frozenset(string.hexdigits)


def _is_hex_token(token: str) -> bool:
    """Return ``True`` if *token* is a non-empty run of hexadecimal digits."""
    return bool(token) and all(char in _HEX_DIGITS for char in token)


def _allowed_keys(section: str) -> set[str]:
    """Return the allowed option names for *section*, or raise if unknown."""
    if section in _SECTION_KEYS:
        return _SECTION_KEYS[section]
    if section.startswith("bus."):
        return _BUS_KEYS
    if section.startswith("region."):
        return _REGION_KEYS
    if section.startswith("extension."):
        return _EXTENSION_KEYS
    raise RiscvConfigError(f"unknown section [{section}]")


class CoreConfig(configparser.ConfigParser):
    """Single configuration object for the RISC-V core (``RC-FR-002``).

    Scalars use the standard ``get``/``getint``/``getboolean`` (``getint``
    accepts ``0x``/``0b``); the complex derived data is exposed as
    :attr:`buses`, :attr:`regions`, :attr:`extensions`, :attr:`isa_string`
    and :attr:`misa`; :meth:`validate` performs the boundary checks.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("inline_comment_prefixes", (";", "#"))
        kwargs.setdefault("interpolation", None)
        super().__init__(*args, **kwargs)
        #: Directory used to resolve relative ``init`` paths (CWD unless loaded).
        self._config_dir = Path.cwd()

    def getint(
        self,
        section: str,
        option: str,
        *,
        raw: bool = False,
        vars: object = None,
        fallback: object = None,
    ):
        """Like ``ConfigParser.getint`` but also accepting ``0x``/``0b`` literals."""
        if not (self.has_section(section) and self.has_option(section, option)):
            return fallback
        try:
            return int(self.get(section, option, raw=raw, vars=vars), 0)
        except (TypeError, ValueError) as exc:
            raise RiscvConfigError(f"[{section}] {option} must be an integer") from exc

    def _get_bool(self, section: str, option: str, default: bool) -> bool:
        """Read a boolean option, converting errors to :class:`RiscvConfigError`."""
        try:
            return self.getboolean(section, option, fallback=default)
        except ValueError as exc:
            raise RiscvConfigError(f"[{section}] {option} must be a boolean") from exc

    def _apply_defaults(self) -> None:
        """Materialise the scalar defaults so the object holds effective values."""
        for section, options in _DEFAULT_OPTIONS.items():
            if not self.has_section(section):
                self.add_section(section)
            for option, value in options.items():
                if not self.has_option(section, option):
                    self.set(section, option, value)
        if not self.has_section("isa"):
            self.add_section("isa")
        if not self.has_option("isa", "base"):
            self.set("isa", "base", "rv32i")

    def _base_isa(self) -> str:
        """Return the configured base ISA name."""
        return self.get("isa", "base", fallback="rv32i")

    @property
    def xlen(self) -> int:
        """Register width, derived from the base ISA (``rv32i`` ⇒ 32)."""
        return _BASE_XLEN[self._base_isa()]

    @property
    def extensions(self) -> tuple[str, ...]:
        """Enabled extensions from the ``[extension.<name>]`` sections."""
        flags: dict[str, bool] = {}
        for section in self.sections():
            if section.startswith("extension."):
                name = section[len("extension.") :].lower()
                flags[name] = self._get_bool(section, "enabled", True)
        enabled = set(AVAIL_EXTENSIONS)
        for name, flag in flags.items():
            if name not in AVAIL_EXTENSIONS:
                raise RiscvConfigError(f"unsupported extension {name!r}")
            if flag:
                enabled.add(name)
            else:
                enabled.discard(name)
        return tuple(ext for ext in AVAIL_EXTENSIONS if ext in enabled)

    @property
    def isa_string(self) -> str:
        """Canonical ISA string, e.g. ``"rv32ic"`` (``RC-FR-034``)."""
        return self._base_isa() + "".join(self.extensions)

    @property
    def misa(self) -> int:
        """Machine ISA register value (``RC-FR-035``)."""
        value = _MXL_32 | _I_BIT
        for extension in self.extensions:
            value |= 1 << MISA_BITS[extension]
        return value

    @property
    def buses(self) -> dict[str, dict]:
        """Named external buses as ``{name: {type, data_width, addr_width}}``."""
        result: dict[str, dict] = {}
        for section in self.sections():
            if not section.startswith("bus."):
                continue
            name = section[len("bus.") :]
            _check_name(name, "bus name")
            result[name] = {
                "type": check_choice(
                    self.get(section, "type", fallback="wishbone"),
                    AVAIL_BUS_TYPES,
                    f"bus {name!r} type",
                    exc=RiscvConfigError,
                ),
                "data_width": _check_width(
                    self.getint(section, "data_width", fallback=32),
                    f"bus {name!r} data_width",
                ),
                "addr_width": _check_width(
                    self.getint(section, "addr_width", fallback=32),
                    f"bus {name!r} addr_width",
                ),
            }
        return result

    @property
    def regions(self) -> tuple[dict, ...]:
        """Validated address-region map (``RC-FR-107``)."""
        bus_map = self.buses
        result: list[dict] = []
        names: set[str] = set()
        for section in self.sections():
            if not section.startswith("region."):
                continue
            name = section[len("region.") :]
            _check_name(name, "region name")
            if name in names:
                raise RiscvConfigError(f"duplicate region {name!r}")
            names.add(name)
            if not (
                self.has_option(section, "base") and self.has_option(section, "size")
            ):
                raise RiscvConfigError(f"region {name!r} requires base and size")
            base = _check_address(
                self.getint(section, "base", fallback=0), f"region {name!r} base"
            )
            size = _check_size(
                self.getint(section, "size", fallback=0), f"region {name!r} size"
            )
            if base % size != 0:
                raise RiscvConfigError(
                    f"region {name!r} base must be aligned to its size"
                )
            perms = check_choice(
                self.get(section, "perms", fallback="ID").upper(),
                AVAIL_PERMS,
                f"region {name!r} perms",
                exc=RiscvConfigError,
            )
            access = check_choice(
                self.get(section, "access", fallback="RW").upper(),
                AVAIL_ACCESS,
                f"region {name!r} access",
                exc=RiscvConfigError,
            )
            target = _check_target(
                self.get(section, "target", fallback="internal"), bus_map, name
            )
            init = self.get(section, "init", fallback=None)
            init_format = self.get(section, "init_format", fallback=None)
            init_fit = self.get(section, "init_fit", fallback=None)
            if init is None:
                if init_format is not None or init_fit is not None:
                    raise RiscvConfigError(
                        f"region {name!r}: init_format/init_fit require init"
                    )
            else:
                if target != "internal":
                    raise RiscvConfigError(
                        f"region {name!r}: init is only valid for internal regions"
                    )
                init = _check_name(init, f"region {name!r} init")
                if init_format is None:
                    raise RiscvConfigError(
                        f"region {name!r}: init requires init_format"
                    )
                init_format = check_choice(
                    str(init_format).lower(),
                    AVAIL_INIT_FORMATS,
                    f"region {name!r} init_format",
                    exc=RiscvConfigError,
                )
                init_fit = check_choice(
                    str(init_fit if init_fit is not None else "strict").lower(),
                    AVAIL_INIT_FIT,
                    f"region {name!r} init_fit",
                    exc=RiscvConfigError,
                )
            result.append(
                {
                    "name": name,
                    "base": base,
                    "size": size,
                    "perms": perms,
                    "access": access,
                    "target": target,
                    "init": init,
                    "init_format": init_format,
                    "init_fit": init_fit,
                }
            )

        ordered = sorted(result, key=lambda region: region["base"])
        for lower, upper in itertools.pairwise(ordered):
            if lower["base"] + lower["size"] > upper["base"]:
                raise RiscvConfigError(
                    f"regions {lower['name']!r} and {upper['name']!r} overlap"
                )
        for region in result:
            if region["base"] + region["size"] > _ADDR_SPACE:
                raise RiscvConfigError(
                    f"region {region['name']!r} exceeds the 32-bit address space"
                )
        return tuple(result)

    def _check_init(self, region: dict) -> None:
        """Magic-check ELF/hex images and size-check raw images (``RC-FR-109``)."""
        path = region["init"]
        if path is None:
            return
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self._config_dir / file_path
        name = region["name"]
        if not file_path.is_file():
            raise RiscvConfigError(f"region {name!r}: init file not found: {file_path}")
        init_format = region["init_format"]
        if init_format == "raw":
            length = file_path.stat().st_size
            if region["init_fit"] == "strict" and length != region["size"]:
                raise RiscvConfigError(
                    f"region {name!r}: raw init size {length} does not match "
                    f"region size {region['size']}"
                )
        elif init_format == "elf":
            with file_path.open("rb") as handle:
                magic = handle.read(4)
            if magic != b"\x7fELF":
                raise RiscvConfigError(
                    f"region {name!r}: init is not an ELF image (bad magic)"
                )
        else:  # hex: only a cheap content check; the reader does the real parse
            with file_path.open("r", encoding="ascii", errors="replace") as handle:
                sample = handle.read(4096)
            tokens = sample.split()
            if not tokens or any(not _is_hex_token(token) for token in tokens):
                raise RiscvConfigError(
                    f"region {name!r}: init does not look like a hex image"
                )

    def validate(self) -> None:
        """Run the boundary checks (``RC-FR-007``); raise on any violation."""
        if self.defaults():
            raise RiscvConfigError("[DEFAULT] section is not supported")
        for section in self.sections():
            unknown = set(self.options(section)) - _allowed_keys(section)
            if unknown:
                raise RiscvConfigError(
                    f"unknown key(s) in [{section}]: {sorted(unknown)}"
                )

        _check_name(self.get("core", "name", fallback="mcu0"), "name")
        check_choice(self._base_isa(), AVAIL_BASES, "base", exc=RiscvConfigError)
        self.extensions
        _check_register_count(self.getint("registers", "count", fallback=32))
        check_choice(
            self.getint("pipeline", "stages", fallback=3),
            AVAIL_PIPELINE_STAGES,
            "stages",
            exc=RiscvConfigError,
        )
        check_choice(
            self.getint("pipeline", "fetch_buffer", fallback=1),
            AVAIL_FETCH_BUFFER,
            "fetch_buffer",
            exc=RiscvConfigError,
        )
        self._get_bool("pipeline", "forwarding", False)
        self._get_bool("core", "interrupts", False)
        self._get_bool("debug", "trace", False)

        region_map = self.regions
        if not region_map:
            raise RiscvConfigError("at least one region is required")
        for region in region_map:
            self._check_init(region)

        reset = _check_address(
            self.getint("core", "reset_vector", fallback=0), "reset_vector"
        )
        reset_region = _region_containing(region_map, reset)
        if reset_region is None or "I" not in reset_region["perms"]:
            raise RiscvConfigError("reset_vector must be inside an I region")
        # tohost/fromhost are intercepted special addresses, not memory: they
        # only need to be word-aligned and may be unmapped (RC-FR-111).
        _check_address(self.getint("core", "tohost", fallback=0x1000), "tohost")
        _check_address(self.getint("core", "fromhost", fallback=0x1004), "fromhost")

    @classmethod
    def from_ini(cls, path: object) -> "CoreConfig":
        """Read and validate an INI file (``RC-FR-003``)."""
        cfg = cls()
        try:
            read = cfg.read(path, encoding="utf-8")
        except (OSError, configparser.Error) as exc:
            raise RiscvConfigError(f"cannot read INI file {path!r}: {exc}") from exc
        if not read:
            raise RiscvConfigError(f"cannot read INI file {path!r}")
        cfg._config_dir = Path(path).resolve().parent
        cfg._apply_defaults()
        cfg.validate()
        return cfg

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Mapping[str, object]]) -> "CoreConfig":
        """Read and validate a mapping (``RC-FR-005``)."""
        cfg = cls()
        cfg.read_dict(mapping)
        cfg._apply_defaults()
        cfg.validate()
        return cfg

    def as_dict(self) -> dict:
        """Return the sections (plus derived ``isa_string``/``misa``)."""
        info = {section: dict(self[section]) for section in self.sections()}
        info["isa_string"] = self.isa_string
        info["misa"] = self.misa
        return info

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.as_dict()!r})"
