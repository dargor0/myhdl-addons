# `myhdl_addons.components`

Independent, ISA-neutral, bus-agnostic synthesizable building blocks.  This
document catalogues the **implemented components and how to use them**.

Runtime depends only on `myhdl`.

## The common usage protocol

Every component follows the same four steps:

1. **Construct** it with keyword configuration.  All tunables are
   elaboration-time parameters with defaults; invalid input raises
   `myhdl_addons.common.errors.HdlConfigError` immediately.
2. **Allocate ports** with `ports()`, which returns a `SignalView` — a named
   bag of signals, accessible as attributes (`ports.a`) and by name
   (`ports["a"]`); `ports.names` / `ports.signals` enumerate them.
3. **Elaborate** with `hdl(ports)`, which returns the list of MyHDL instances
   for the configured design.
4. **Introspect** with `as_dict()` (effective configuration) and `repr()`.

Options that are switched off **remove their ports** (zero overhead): e.g. a
combinational component has no `clk`, and `Mux(valid=False)` has no `valid`
port.  Feature subsets accept either canonical integer codes or their string
names (e.g. `Alu(ops=["ADD", "SUB"])`).

```python
from myhdl_addons.components import Mux

mux = Mux(width=8, n=4)          # validated configuration
ports = mux.ports()              # named signals: sel, inputs, y
dut = mux.hdl(ports)             # MyHDL instances; simulate or instantiate
```

`AVAIL_*` constants (`AVAIL_OPS`, `AVAIL_FLAGS`, `AVAIL_OUTPUTS`, `MODES`,
`MODE_NAMES`, `STRUCTURES`, `PRIORITIES`, `INTERFACES`, `STREAM`, `WR_RD`,
`WRITE_MODES`, `READ_FIRST`, `WRITE_FIRST`, `NO_CHANGE`) name the allowed
values and are re-exported from `myhdl_addons.components`.

---

## Combinational building blocks

Combinational components offer a uniform **`registered`** option: `registered=0`
is pure combinational (no clock), `registered=1` adds an output register
(`clk`/`reset`, plus `en` when enabled) and one cycle of latency, with
`reset_value` as the registered reset.  Registered components use the `reset`
port; sequential components use active-low `resetn`.

### `Alu` — arithmetic/logic unit

`Alu(width=32, ops=None, flags=None, registered=False, en=False, reset_value=0, reset_signal=None)`

- `ops` ⊆ `AVAIL_OPS` = `NOP, ADD, SUB, AND, OR, XOR, SLT, SLTU, PASS_A, PASS_B`
  (default all; `NOP` is code 0).  No shift operations — use `BarrelShifter`.
- `flags` ⊆ `AVAIL_FLAGS` = `zero, lt, ltu, carry`.
- Ports: `a`, `b`, `op`, `y`; one port per enabled flag; registered adds
  `clk`/`reset` (+`en`).
- **Usage:** the `op` value is the index into the enabled op tuple; get it with
  `alu.get_op_intmap()["ADD"]`.  `SLT` is signed, `SLTU` unsigned; `carry` is
  the add carry / subtract borrow.  New ops can be attached with
  `alu.register_op(name, callback)`.

### `BarrelShifter` — shifts and rotates

`BarrelShifter(width=32, modes=None, structure="logarithmic", registered=0, en=False, reset_value=0, reset_signal=None, shamt_const=None, shamt_bits=None, shamt_mode="modulo")`

- `modes` ⊆ `MODES` = `SLL, SRL, SRA, ROL, ROR`, selected on the `mode` port by
  their canonical codes `0..4` (`MODE_NAMES` maps code → name).
- `structure` ∈ `STRUCTURES` = `logarithmic / two_stage / serial`.
- `shamt_mode` ∈ `modulo / saturate / zero` (out-of-range shift handling).
- `shamt_const` fixes the shift amount and **omits** the `shamt` port;
  `shamt_bits` overrides the amount width (default `ceil(log2 width)`; in
  `saturate` mode the `shamt` port is one bit wider).
- Ports: `data`, `mode`, `y`, `shamt` (unless `shamt_const`); registered adds
  `clk`/`reset` (+`en`).
- **Usage:** drive `mode` with the canonical code; a disabled or unknown mode
  yields `y = 0`.

### `Incrementer` — signed stepper

`Incrementer(width=32, steps=None, load_enable=True, wrap_mode="wrap", carry=False, registered=0, reset_value=0, reset_signal=None)`

- `steps` is a non-empty tuple of signed constants (default `(1,)`); the
  `step_sel` port appears when there is more than one step.
- `wrap_mode` ∈ `WRAP_MODES` = `wrap / saturate`.
- Ports: `a`, `en`, `y`; `step_sel`; `load`/`load_value`; `carry`; registered
  adds `clk`/`reset` (+`en`).
- **Usage:** `y = a + steps[step_sel]`; `load` overrides `en`/`step_sel`;
  `en=0` holds `a`; an out-of-range `step_sel` holds `a`.

### `Comparator` — comparison flags

`Comparator(width=32, outputs=None, signed=True, registered=False, en=False, reset_value=0, reset_signal=None)`

- `outputs` ⊆ `AVAIL_OUTPUTS` = `eq, ne, lt, ltu, gt, gtu, ge, le`.
- `signed` makes `lt/gt/ge/le` two's-complement; `ltu/gtu` are always unsigned.
- Ports: `a`, `b`; one port per enabled flag; registered adds `clk`/`reset` (+`en`).

### `Mux` — binary-select multiplexer

`Mux(width, n, default_value=0, valid=False, registered=False, en=False, reset_value=0, reset_signal=None)`

- Ports: `inputs` (a tuple of `n` signals, `ports.inputs[i]`), `sel`, `y`;
  optional `valid`; registered adds `clk`/`reset` (+`en`).
- **Usage:** `y = inputs[sel]` while `sel < n`, otherwise `default_value`;
  `valid = (sel < n)`.  `mux.sel_bits` gives the `sel` width.

### `OneHotMux` — one-hot/OR-reduce multiplexer

`OneHotMux(width, n, valid=False, strict=False, registered=False, en=False, reset_value=0, reset_signal=None)`

- Ports: `inputs`, `sel` (`n` bits), `y`; optional `valid`; registered adds
  `clk`/`reset` (+`en`).
- **Usage:** `y` is the OR of every `inputs[i]` whose `sel[i]` is set;
  `valid` is `sel != 0`, or with `strict=True` exactly one bit set.

### `Decoder` — binary → one-hot

`Decoder(n, en=False, registered=0, reset_value=0, reset_signal=None)`

- Ports: `sel` (`dec.sel_bits`), `onehot` (`n` bits), optional `en`, registered
  adds `clk`/`reset`.
- **Usage:** `onehot = 1 << sel` when `sel < n`, else `0`; `en=0` forces zero.

### `PriorityEncoder` — bit vector → index

`PriorityEncoder(n, priority="low", en=False, registered=0, reset_value=0, reset_signal=None)`

- `priority` ∈ `PRIORITIES` = `low / high` (lowest or highest set bit wins).
- Ports: `din` (`n` bits), `index` (`pe.index_bits`), `valid`, optional `en`,
  registered adds `clk`/`reset`.
- **Usage:** `index` is the winning set bit; `valid = (din != 0)` (forced low
  when `en=0`).

### `AddressDecoder` — address-window → one-hot selects

`AddressDecoder(adr_width=32, windows=None, en=False, valid=False, registered=0, reset_value=0, reset_signal=None)`

- `windows` is a non-empty list of **non-overlapping** `(base, size)` address
  windows; window `i` drives output `sel{i}`.  Overlap, out-of-range windows or
  an empty list raise `HdlConfigError` at construction.
- Ports: `adr`; `sel0 … sel{n-1}`; optional `en`, `valid`; registered adds
  `clk`/`reset`.
- **Usage:** `sel{i}` asserts while `base_i <= adr < base_i + size_i` (and
  `en=1`); a gap/out-of-range address yields all-zero selects; `valid` is any
  select asserted.  `ad.num_windows` gives `n`.

```python
from myhdl_addons.components import AddressDecoder

dec = AddressDecoder(adr_width=16, windows=[(0x0000, 0x100), (0x1000, 0x100)])
ports = dec.ports()          # adr, sel0, sel1
```

---

## Sequential building blocks

Sequential components always have `clk`; resets are **active-low `resetn`**
unless stated otherwise.

### `Register` — plain and pipeline register

`Register(fields=None, en=True, flush=False, load=False, reset_enable=True, reset_values=None, flush_values=None, load_values=None, init=None)`

- `fields` is a list of `(name, width)` pairs (default `[("q", 32)]`).
- Ports: `clk`, `resetn`; per field `d_<name>` and `q_<name>`; `en`, `flush`,
  `load` when enabled.
- **Usage:** control priority is `reset > flush > load > en > hold`; `en=0`
  holds, `flush`/`load` force their configured per-field values.  A **pipeline
  register** is simply a multi-field `Register` with `flush` enabled.

### `Counter` — sequential stepper

`Counter(width=32, steps=None, min=0, max=None, wrap_mode="wrap", prescaler=1, load_enable=True, reset_value=0, tick=True)`

- The sequential counterpart of `Incrementer` (same `steps`/`step_sel`/
  `wrap_mode`/`load` semantics).
- Ports: `clk`, `resetn`, `en`, `count`; `step_sel`; `load`/`load_value`;
  optional `tick`.
- **Usage:** counts within `[min, max]`; `prescaler` divides the input `en`;
  `tick` asserts at the terminal count.

### `RegisterFile` — multi-port register bank

`RegisterFile(width=32, depth=32, read_ports=2, write_ports=1, read_latency=0, write_mode="read_first", zero_reg_fix_value=None, reset_enable=True, reset_value=0, init=None, byte_write=False)`

- Ports: `clk`, `resetn`; per write port `we{p}`/`waddr{p}`/`wdata{p}` (and
  `wstrb{p}` with `byte_write`); per read port `raddr{p}`/`rdata{p}`.
- `write_mode` ∈ `WRITE_MODES` = `read_first / write_first / no_change` for
  same-address accesses; `read_latency` is `0` (async) or `1` (registered).
- `zero_reg_fix_value` (e.g. `0`) makes index 0 a read-only constant (writes
  ignored); `None` leaves index 0 as ordinary storage.
- `byte_write=True` enables per-lane write strobes (`width` must be a multiple
  of 8).

### `SyncRam` — read/write memory

`SyncRam(width, depth, read_latency=1, write_mode="read_first", read_ports=1, write_ports=1, byte_write=0, init=None, output_register=False)`

- Ports: `clk`, `resetn`; per write port `we{p}`/`waddr{p}`/`wdata{p}` (+
  `wstrb{p}`); per read port `raddr{p}`/`rdata{p}`.
- `byte_write` is `0` (off) or `width/8`.  `init` loads an optional image.
- **Usage:** total read latency is `read_latency + output_register`.  Reset
  does **not** clear contents; use `init` to define the power-up image.

### `SyncRom` — read-only memory

`SyncRom(width, depth, init, read_latency=1, read_ports=1, output_register=False)`

- `init` is **required** and must have length `depth`.
- Ports: `clk`, `resetn`; per read port `raddr{p}`/`rdata{p}`.
- Total read latency is `read_latency + output_register`.

### `Fifo` — synchronous FIFO / skid buffer

`Fifo(width, depth, interface="wr_rd", fall_through=False, almost_full=0, almost_empty=0, count=False, flush=False, registered_outputs=False)`

- `interface` ∈ `INTERFACES` = `wr_rd` (native) or `stream` (valid/ready).
- Ports (`wr_rd`): `clk`, `resetn`, `wr_en`, `wdata`, `rd_en`, `rdata`, `full`,
  `empty`.
- Ports (`stream`): `clk`, `resetn`, `valid_in`, `ready_in`, `data_in`,
  `valid_out`, `ready_out`, `data_out`.
- Optional `count`, `almost_full`, `almost_empty`, `flush`.
- **Usage:** `fall_through=True` gives a first-word-fall-through (combinational)
  read; `registered_outputs=True` adds an output register stage.  A **skid
  buffer** is `Fifo(depth=2, interface="stream")`.
