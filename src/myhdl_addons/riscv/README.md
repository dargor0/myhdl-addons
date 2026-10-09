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

Ready-made example files ship outside the package source: `config/riscv_minimal.ini`,
`config/riscv_example.ini` (loads the demo image `share/riscv_firmware.hex`) and
`config/riscv_tests.ini` (loads the example ISA test `share/riscv_isa_test.hex`,
which writes pass to `tohost`).

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
| `extensions` | `Extension` / `ExtensionRegistry` — the ISA plug-in mechanism |
| `rvc` | `RvcDecompressor` and the `CExtension` front-end plug-in |
| `fetch` | `FetchUnit` — instruction front-end (buffer/refill, straddle, waits) |
| `immgen` | `ImmGen` — I/S/B/U/J immediate generation |
| `decoder` | `InstructionDecoder` / control unit |
| `branch` | `BranchUnit` and `jalr_target` |
| `lsu` | `LoadStoreUnit` — load/store sizes, extension, byte strobes |
| `pc` | `ProgramCounter` — sequential advance, load and link values |
| `router` | `MemoryRouter` — address-region map, fetch/data clients, internal memories |
| `busmaster` | `BusMaster` — two Q31 clients arbitrated onto one Wishbone master |
| `core` | `RiscvCore` — assembled non-pipelined RV32I core (multi-cycle) |
| `iss` | `RV32ICIss` — plain-Python architectural golden model (simulation-only) |
| `sim` | simulation-only testbench helpers: `MemoryImage` (ELF32/`.hex`), `MemoryBfm`, `SignatureChecker` |
| `tohost` | `ToHost` — `tohost`/`fromhost` interception and halt |

Every synthesizable block has unit, Verilog/VHDL conversion, cosim and
synthesis tests. The `RiscvCore` assembles them into a working RV32IC machine
and passes a per-retire differential against the Python ISS; the CSRs are added
as a later extension.

## Running the ISA tests (L1)

`tests/test_riscv_l1.py` always runs the example ISA test
(`config/riscv_tests.ini`). It additionally runs the `riscv-tests`
`rv32ui`/`rv32uc` suites when their prebuilt ELFs are available; otherwise it
skips. The reference toolchain is the xPack **`riscv-none-elf-gcc`**.

Build the suite on Ubuntu:

```sh
# 1. Toolchain (xPack GNU RISC-V Embedded GCC, linux-x64).
#    Pick a release from
#    https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases
VER=14.2.0-3
curl -L -o /tmp/riscv-none-elf.tar.gz \
  "https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v$VER/xpack-riscv-none-elf-gcc-$VER-linux-x64.tar.gz"
mkdir -p "$HOME/opt" && tar -xzf /tmp/riscv-none-elf.tar.gz -C "$HOME/opt"
export PATH="$HOME/opt/xpack-riscv-none-elf-gcc-$VER/bin:$PATH"
#    (or: sudo apt install gcc-riscv64-unknown-elf  and use that prefix below)

# 2. Build riscv-tests (produces isa/rv32ui-p-* and isa/rv32uc-p-*).
git clone https://github.com/riscv-software-src/riscv-tests
cd riscv-tests
git submodule update --init --recursive
autoconf
RISCV_PREFIX=riscv-none-elf- ./configure    # or riscv64-unknown-elf-
make
export RISCV_TESTS_DIR="$PWD/isa"

# 3. Run.
scripts/run_tests.sh 85 tests/test_riscv_l1.py
```

`RISCV_TESTS_DIR` must contain the built `rv32ui-p-*` / `rv32uc-p-*` ELFs (the
runner reads each ELF's entry and `tohost`/`fromhost` symbols and checks the
`tohost` signature).

## See also

- [`CONFIG.md`](CONFIG.md) — the INI configuration reference.
- [`../components/README.md`](../components/README.md) — the reusable blocks the core is built from.
- [`../wishbone/README.md`](../wishbone/README.md) — the primary bus transport.
