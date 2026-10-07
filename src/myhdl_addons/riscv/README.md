# `myhdl_addons.riscv`

A small, readable **RV32I + C (compressed)** RISC-V core for microcontrollers,
written in MyHDL 0.11 and assembled from the independent
[`myhdl_addons.components`](../components/README.md) library and the
[`myhdl_addons.bus_common`](../bus_common/README.md) /
[`myhdl_addons.wishbone`](../wishbone/README.md) bus layers.

The synthesizable parts convert to **Verilog and VHDL**. The core is
little-endian (ILP32); the C extension is enabled by default and can be
disabled for a plain RV32I core.

> Status: the configuration foundation (`CoreConfig`, INI loading, the
> `RiscvError` hierarchy) is in place; the RTL blocks and the assembled
> `RiscvCore` are being added. This document is updated as the package grows.

## Quick start

Every core detail lives in a `CoreConfig` (a `configparser.ConfigParser`
subclass), loaded from an INI file or built programmatically. Scalars are read
through the standard `get*` methods; the complex derived data is exposed as
properties:

```python
from myhdl_addons.riscv import CoreConfig

cfg = CoreConfig.from_ini("mycore.ini")  # schema in CONFIG.md
print(cfg.isa_string)  # 'rv32ic'
print(hex(cfg.misa))  # 0x40000104
print(len(cfg.regions))  # number of memory regions

cfg = CoreConfig.from_mapping(
    {  # ...or programmatically
        "core": {"reset_vector": "0x0", "tohost": "0x1000", "fromhost": "0x1004"},
        "region.ram": {
            "base": "0x0",
            "size": "0x10000",
            "perms": "ID",
            "access": "RW",
            "target": "internal",
        },
    }
)
```

Ready-made example files ship outside the package source: `config/riscv_minimal.ini`
and `config/riscv_example.ini` (the latter loads the demo image
`share/riscv_firmware.hex`).

The full INI file schema (sections, keys, defaults, validation and a complete
example) is in [`CONFIG.md`](CONFIG.md).

Bad configuration is rejected immediately with a `RiscvConfigError` (a
`HdlConfigError`, catchable at the usual levels):

```python
from myhdl_addons.riscv import CoreConfig, RiscvConfigError

try:
    CoreConfig.from_mapping(
        {
            "core": {"reset_vector": "0x0", "tohost": "0x1000", "fromhost": "0x1004"},
            "region.ram": {
                "base": "0x0",
                "size": "0x3000",  # not a power of two
                "perms": "ID",
                "access": "RW",
                "target": "internal",
            },
        }
    )
except RiscvConfigError as exc:
    ...
```

## Package contents

| Module | Provides |
|---|---|
| `config` | `CoreConfig` (a `ConfigParser` subclass) with `regions`/`buses`/`extensions`/`isa_string`/`misa` properties, `validate()`, and the allowed-value constants |
| `errors` | `RiscvError`, `RiscvConfigError`, `RiscvTypeError` |

The RTL blocks — decoder/control unit, RVC decompressor, immediate generator,
fetch unit, load/store unit, CSRs, memory fabric and the assembled
`RiscvCore` — are added incrementally, each with its own tests and a
Verilog/VHDL conversion check.

## See also

- [`CONFIG.md`](CONFIG.md) — the INI configuration reference.
- [`../components/README.md`](../components/README.md) — the reusable blocks the core is built from.
- [`../wishbone/README.md`](../wishbone/README.md) — the primary bus transport.
