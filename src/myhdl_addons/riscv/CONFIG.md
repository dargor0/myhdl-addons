# RISC-V core configuration (`CONFIG.md`)

This document describes the **INI file** that configures the core: its
sections and keys, their defaults and allowed values, the value formats, and
examples.

Invalid files are rejected: unknown sections or keys, malformed values, or
inconsistent settings are errors. A valid file must define **at least one
`[region.<name>]`** (there is no default memory map) and place `reset_vector`
inside an executable region.

## Memory model

Every instruction fetch and load/store is dispatched by **address** through a
**region map**:

- Each **region** is a contiguous, non-overlapping address window with a
  **backend**: an internal on-chip memory or a named external bus.
- There is no Harvard/Von Neumann switch — the region map subsumes both, and
  an all-internal (0-bus) core is a valid configuration.
- A region may allow **instructions (`I`)**, **data (`D`)** (including
  memory-mapped peripherals), or **both (`ID`)**; so a preloaded RAM region can
  hold code and data, and a ROM region can be instruction-only.
- Accessing an unmapped address, fetching from a non-`I` region, loading or
  storing to a non-`D` region, or writing an `RO` region raises the
  corresponding **access fault**.

## File layout

| Section | Purpose |
|---|---|
| `[core]` | identity, reset vector, interrupt inputs |
| `[isa]` | base ISA and register width |
| `[extension.<name>]` | one section per optional ISA extension |
| `[registers]` | general-purpose register file |
| `[pipeline]` | pipeline depth and instruction buffering |
| `[bus.<name>]` | one section per external bus (0..N) |
| `[region.<name>]` | one section per address region (1..N) |
| `[debug]` | simulation/debug options |

## `[core]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `name` | string | `mcu0` | instance name; must be non-empty |
| `reset_vector` | address | `0x00000000` | first instruction fetch; must lie in an executable region |
| `tohost` | address | `0x00001000` | halt / result address polled by the testbench |
| `fromhost` | address | `0x00001004` | host-to-target input address |
| `interrupts` | bool | `false` | expose the `msip`/`mtip`/`meip` machine interrupt inputs |

A write to `tohost` halts the core: bit 0 set means **pass**, otherwise the
exit code is `value >> 1`. `fromhost` is read by the program as host input.
These are **special addresses intercepted by the core**: they need not be
mapped to any region — a store to `tohost` or a load from `fromhost` is
handled by the core rather than the memory system.

## `[isa]`

| Key | Type | Default | Allowed |
|---|---|---|---|
| `base` | string | `rv32i` | `rv32i` |

The register width (XLEN) is implied by `base` (`rv32i` ⇒ 32), so there is no
separate `xlen` key. Only `rv32i` is accepted today. RV64 and **alternate base
integer ISAs** (for example RV32E) are **not supported yet**; they may be added
in the future as further `base` configurations that reuse the same core.

The core's **ISA string** (e.g. `rv32ic`) is *derived* from `base` plus the
extensions enabled in `[extension.<name>]`; there is no ISA-string input key.

## `[extension.<name>]`

One section per optional extension. The only extension currently supported is
**C** (compressed 16-bit instructions), which is enabled by default:

```ini
[extension.c]
enabled = true
```

Set `enabled = false` to disable C and obtain a plain RV32I core (any 16-bit
encoding then becomes illegal). If the section is absent, the extension keeps
its default (C stays on). Unknown extension names are rejected.

## `[registers]`

| Key | Type | Default | Allowed |
|---|---|---|---|
| `count` | int | `32` | `32` |

`x0` is hardwired by the core; the register file itself is a plain 32-entry
bank.

## `[pipeline]`

| Key | Type | Default | Allowed |
|---|---|---|---|
| `stages` | int | `3` | `1`, `2`, `3` |
| `fetch_buffer` | int | `1` | `0`, `1`, `2` |
| `forwarding` | bool | `false` | |

- `stages`: `1` is the non-pipelined bring-up core, `2` and `3` select the
  pipelined variants (`3` is the default MCU configuration).
- `fetch_buffer`: instruction-buffer depth in 16-bit parcels. `0` re-fetches a
  straddling 32-bit instruction, `1` buffers one parcel, `2` buffers a full
  32-bit word.
- `forwarding`: when `true`, the pipelined core forwards results to reduce
  stalls (a load-use dependency still stalls one cycle). Ignored when
  `stages = 1`.

## `[bus.<name>]`

One section per external bus. The core may have **zero or more** buses; each
becomes a master port that is routed to by the regions whose `target` names
it.

| Key | Type | Default | Allowed |
|---|---|---|---|
| `type` | string | `wishbone` | `wishbone`, `axi` |
| `data_width` | int | `32` | `32` |
| `addr_width` | int | `32` | `32` |

A bus that is reachable by both instruction and data regions is arbitrated by
the core (fetch stalls cleanly while a data access owns the bus); a bus used
by only one client needs no arbitration.

## `[region.<name>]`

One section per address region. Regions must be **non-overlapping**; `size`
must be a **power of two**, and `base` must be **aligned to `size`**.

| Key | Type | Default | Allowed / notes |
|---|---|---|---|
| `base` | address | — | start address; aligned to `size` |
| `size` | int | — | power of two; bytes |
| `perms` | string | `ID` | `I` (execute), `D` (load/store), `ID` (both) |
| `access` | string | `RW` | `RO` (writes fault) or `RW` |
| `target` | string | `internal` | `internal` or `bus:<name>` |
| `init` | string | — | path to a preload image file (requires `init_format`) |
| `init_format` | string | — | `elf`, `hex` or `raw` (required with `init`) |
| `init_fit` | string | `strict` | `strict` (exact size) or `truncate` |

**Internal regions** (`target = internal`):

- generated as an on-chip memory from the generic components:
  `access = RO` → `SyncRom`, `access = RW` → `SyncRam`;
- depth is `size / 4` words;
- `init` is a **file path** (no inline contents; a missing file is an error);
  `init_format` selects the reader: `elf` (ELF32 — the ELF magic is checked
  when the file is loaded), `hex` (hex text — the content is checked to look
  like hex), or `raw` (the whole file as little-endian bytes);
- `init_fit`: for `raw`, `strict` errors unless the file exactly matches the
  region `size`, while `truncate` truncates overflow / zero-fills a short file;
  for `elf` and `hex` the size/format enforcement is performed by their readers;
- when `perms = ID`, a **dual-port** memory is generated (two read ports; a
  RAM also has one write port) so instruction fetch and data access never
  contend. Otherwise the memory is single-port and needs no arbitration;
- internal memory is **private** to the core (it is not visible on any bus).

**External regions** (`target = bus:<name>`):

- the access is routed to the named bus, and its own address map selects the
  slave;
- `access = RO` is enforced by the core (stores raise an access fault without
  reaching the bus).

Any region may be marked `ID`, so a single preloaded RAM region can run a
program **and** hold its data.

## `[debug]`

| Key | Type | Default | Notes |
|---|---|---|---|
| `trace` | bool | `false` | emit a retirement trace during simulation |

## Value formats

- Integers may be decimal (`4096`) or hexadecimal (`0x1000`).
- Booleans accept `true`/`false` (case-insensitive).
- Addresses must be word-aligned (a multiple of 4).
- Region `size` must be a power of two, and `base` a multiple of `size`.
- The core is **little-endian**: `raw` images are little-endian bytes, `hex`
  tokens are 32-bit words, and `elf` images must be little-endian (`ELFDATA2LSB`).

## Minimal example

A self-contained core with a single internal RAM region and no bus (C is on by
default):

```ini
[core]
reset_vector = 0x00000000
tohost   = 0x00001000
fromhost = 0x00001004

[region.ram]
base   = 0x00000000
size   = 0x00010000
perms  = ID
access = RW
target = internal
```

## Complete example

```ini
[core]
name = mcu0
reset_vector = 0x00000000
tohost   = 0x00010000
fromhost = 0x00010004
interrupts = false

[isa]
base = rv32i

[extension.c]
enabled = true

[registers]
count = 32

[pipeline]
stages = 3
fetch_buffer = 1
forwarding = false

[bus.mem]
type = wishbone

[bus.periph]
type = axi

[region.rom]
base   = 0x00000000
size   = 0x00004000
perms  = I
access = RO
target = internal
init        = firmware.hex
init_format = hex

[region.sram]
base   = 0x00010000
size   = 0x00004000
perms  = ID
access = RW
target = internal

[region.dram]
base   = 0x40000000
size   = 0x10000000
perms  = ID
access = RW
target = bus:mem

[region.periph]
base   = 0x80000000
size   = 0x00100000
perms  = D
access = RW
target = bus:periph

[debug]
trace = false
```

This configuration maps a ROM and an SRAM on-chip, a large DRAM on the
`mem` Wishbone bus, and peripherals on the `periph` AXI bus — four regions,
two buses, two internal memories.
