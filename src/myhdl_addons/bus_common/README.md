# `myhdl_addons.bus_common`

The pieces that every bus library (`wishbone`, `axi`, and other fabrics) shares:
base classes, services, records and cross-cutting rules. It contains **no
protocol behaviour** — no signal names, opcodes or handshake encodings. Each
per-bus sub-package subclasses these types and adds its own signals and
handshakes.

Layering is one-way: **per-bus → `bus_common`**, and `bus_common` never imports
a per-bus module. `bus_common` may reuse the independent
`myhdl_addons.components` (e.g. `AddressDecoder`).

```python
import myhdl_addons.bus_common as bc
```

---

## Blocks at a glance

| Module | Public API | Purpose |
|---|---|---|
| `errors` | `BusError`, `BusConfigError`, `BusTypeError`, `BusProtocolError` | Common exception hierarchy; each bus defines a subclass. |
| `params` | `check_positive_int`, `check_power_of_two`, `check_multiple_of`, `check_range`, `check_alignment`, `register_preset`, `get_preset`, `list_presets` | Elaboration-time validation helpers and the named-preset registry. |
| `bits` | `byte_count`, `enable_width`, `all_enables` | Byte-lane / enable-width helpers from `(data_width, gran)`. |
| `records` | `BusStatus`, `Direction`, `TransactionRecord`, `ErrorEvent`, `ContentionEvent` | Common transaction/event records with `as_dict()` serialization. |
| `trace` | `Trace` | Simulation-only hook registry (signals, transactions, errors, contention). |
| `checks` | `Severity`, `Check`, `CheckRegistry`, `DEFAULT_CHECKS`, `check_signal_type/width/direction/address_range` | Elaboration-time check framework. |
| `port` | `PortBase`, `ViewBase` | Raw endpoint signal set and directional (`_o`/`_i`) views. |
| `interconnect` | `InterconnectContext`, `InterconnectBase`, `arbiter_block`, `decoder_block` | Pluggable fabric strategy base and bus-agnostic fabric helpers. |
| `arbiter` | `ArbiterBase`, `FixedPriorityArbiter`, `RoundRobinArbiter`, `fixed_priority_arbiter`, `round_robin_arbiter` | Protocol-agnostic request/grant arbiters. |
| `addrmap` | `AddressMap`, `address_decoder` | Ordered, non-overlapping slave windows and a decoder (reuses the `AddressDecoder` component). |
| `container` | `BusContainerBase` | Owns ports, the address map and builds the fabric. |
| `regfile` | `RegisterEngine`, `CSRMap`, `RegisterSpec`, `READ`, `WRITE`, `RO`, `bitfield`, `bitfield_set` | Generic register/CSR engine (bus-independent). |
| `bfm` | `BFMBase`, `StreamBFMBase` | Simulation-only bus-functional-model base classes. |
| `adapter` | `AdapterBase` | Base for cross-bus translators plus a loopback self-check. |

---

## `errors` — exception hierarchy

All exception classes live in the single shared location
`myhdl_addons.common.errors`; `myhdl_addons.bus_common` re-exports the bus
aliases so imports keep working:

```python
class HdlError(Exception): ...


class BusError(HdlError): ...


class BusConfigError(HdlConfigError, BusError): ...  # invalid config


class BusTypeError(HdlTypeError, BusError): ...  # wrong/dangling MyHDL type


class BusProtocolError(HdlProtocolError, BusError): ...  # protocol rule broken
```

Each per-bus library adds its own subclasses there too (e.g.
`WishboneConfigError(BusConfigError, WishboneError)`), so callers can catch the
generic, bus-level or library-level type.

## `params` — validation and presets

Validation helpers reject bad geometry at elaboration time and return the value
on success (so they can be used inline). The preset registry stores named
parameter dictionaries that a bus extends with protocol defaults:

```python
from myhdl_addons.bus_common import register_preset, get_preset, list_presets

register_preset("small", {"data_width": 8})
get_preset("small")  # -> {"data_width": 8}
```

## `bits` — enable/granularity helpers

```python
byte_count(data_width)  # number of 8-bit bytes
enable_width(data_width, gran=8)  # number of enable lanes (data_width // gran)
all_enables(data_width, gran=8)  # integer with every lane set
```

## `records` — transactions and events

```python
BusStatus: OK | ERROR | RETRY | DENIED | EXOKAY
Direction: READ | WRITE | ATOMIC | STREAM
```

- `TransactionRecord(port, address, direction, length, data, status, extra)` —
  plus `start`, `end`, `latency`. `as_dict()` yields JSON-friendly data
  (enums become their string value).
- `ErrorEvent(port, address, kind, extra)`.
- `ContentionEvent(detail, port, extra)`.

All three carry an `extra` mapping so a per-bus library can attach fields
without breaking the schema.

## `trace` — simulation/debug hooks

`Trace` is a registry of callbacks, never synthesized. It is disabled by
default and adds nothing when disabled.

```python
trace = Trace(enabled=True)
trace.transaction(lambda rec: print(rec.as_dict()))
trace.error(lambda ev: ...)
trace.contention(lambda ev: ...)
trace.signal(clk, name="clk", callback=lambda n, o, v, t: ...)

trace.enable()
trace.disable()  # global
trace.disable("transaction")
trace.enable("transaction")  # per hook
```

Producers call `emit_transaction/emit_error/emit_contention`. Signal monitors
are produced by `monitors()`, which is itself an `@block` — include it in the
top-level block (the container does this automatically).

## `checks` — elaboration-time check framework

```python
from myhdl_addons.bus_common import (
    Check,
    CheckRegistry,
    Severity,
    DEFAULT_CHECKS,
    check_signal_type,
    check_signal_width,
    check_signal_direction,
    check_address_range,
)
```

- `Check(name, func, severity, enabled, description)` wraps a check function.
- `CheckRegistry` supports registering, enabling/disabling globally or per check,
  and running by name. `DEFAULT_CHECKS` ships the four common checks.
- The common functions raise `BusTypeError`/`BusConfigError` on failure and are
  reused by every per-bus assertion set.

## `port` — ports and directional views

A `PortBase` holds the raw signals of one endpoint; a `ViewBase` exposes
directional aliases (`_o`/`_i`) and the canonical `.clk`/`.rst` accessors:

```python
port = PortBase("m0", clk=clk, rst=rst, data_width=32)
port.add("cyc", Signal(bool(0)))
port.signals  # {"cyc": <Signal>}
port.geometry  # {"data_width": 32}

view = ViewBase(port, clk, rst)
view.alias("cyc_o", "cyc")  # view.cyc_o is port.cyc
view.alias_direction("adr", "out", "adr")  # view.adr_o is port.adr
```

## `interconnect` — strategy base and helpers

- `InterconnectContext` carries the ports, address map, geometry, clock/reset
  and optional-signal flags into a strategy. Per-bus containers override
  `make_context()` to add protocol-specific attributes.
- `InterconnectBase` is abstract; a strategy implements `build(ctx)` and may
  override `validate(ctx)` to reject an illegal topology at elaboration.
- `arbiter_block(...)` and `decoder_block(...)` compose the common arbiter and
  decoder; both are `@block` helpers returning fabric instances.

## `arbiter` — request/grant arbiters

`FixedPriorityArbiter` (combinational, lowest index wins) and
`RoundRobinArbiter(reset_active=1)` (registered, starvation-free). Both expose
`block(clk, rst, requests, grants)` operating on parallel lists of
`Signal(bool)`.

- `reset_active` selects the asserted level of `rst` at elaboration; `None`
  ignores reset entirely.
- Requests/grants are parallel lists of `Signal(bool)`. Inside a fabric the
  ports are packed into vectors and these lists are kept internal.

```python
FixedPriorityArbiter().block(clk, rst, requests, grants)
round_robin_arbiter(clk, rst, requests, grants, reset_active=1)
```

## `addrmap` — windows and decoder

```python
amap = AddressMap(adr_width=16)
amap.add(0x0000, 0x100, "rom")
amap.add(0x1000, 0x100, "csr")
amap.regions  # [(base, size, name), ...]
amap.bases()
amap.sizes()
amap.names()
amap.find(0x1050)  # index or None
address_decoder(adr, selects, amap.bases(), amap.sizes())  # @block
```

Overlapping or out-of-range windows raise at elaboration.
`address_decoder` **adopts the caller's** `adr`/`selects` signals and reuses the
independent `myhdl_addons.components.AddressDecoder` component, so it converts
to Verilog/VHDL.

## `container` — the bus container base

`BusContainerBase` owns the ports, the `AddressMap`, the `Trace` and the
selected strategy. A per-bus subclass sets the class attributes
(`reset_name`, `reset_active`, `handshake`, `port_cls`, `master_view_cls`,
`slave_view_cls`) and may override the port/view factories and `make_context()`.

```python
bus = MyBus(clk, rst, data_width=32, adr_width=16, interconnect=MyFabric())
m = bus.add_master("m0")
s = bus.add_slave(base=0, size=0x100, name="csr")
fabric = bus.build()  # @block: fabric block + trace monitors
```

- `add_master(name=None) -> MasterView` and
  `add_slave(base=0, size=None, name=None) -> SlaveView` create ports/views and
  register the slave window; adding after `build()` raises.
- `build(interconnect=None)` is an `@block`: it requires ≥1 master and ≥1 slave,
  validates that the strategy is an `InterconnectBase`, delegates routing to
  `interconnect.build(context)` and appends the trace monitors.
- `trace`, `address_map`, `masters`, `slaves` and `metadata()` expose state.

## `regfile` — generic register/CSR engine

`RegisterEngine` is bus-independent: it is driven by a small synchronous
request interface (`req`, `we`, `addr`, `wdata`, optional `wstrb`) and produces
`rdata`/`ack`, plus per-register `.wr[name]`/`.rd[name]` strobes and stored
`.signals[name]`.

```python
from myhdl_addons.bus_common import RegisterEngine, READ, WRITE, RO

eng = RegisterEngine(width=32, gran=8)
eng.add_write(0x00, "CTRL", init=1)  # stored, writable
eng.add_ro(0x04, "ID", init=0xCAFE)  # stored, read-only
eng.add_read(0x08, "STATUS", source=...)  # peripheral drives eng.signals["STATUS"]
eng.build(clk, rst, req, we, addr, wdata, rdata, ack, wstrb=wstrb)  # @block
```

- `reset_active` chooses the asserted level of `rst`; `None` ignores reset.
- `wstrb` enables per-lane (byte) writes; a register added with `w1c=True` is
  write-1-to-clear.
- The engine converts: each register has its own clocked cell, and the address
  compare plus the W1C/byte-strobe merge are performed **inside** the clocked
  cell, so a new `addr`/`wdata` presented with the clock edge is sampled in the
  same cycle.

`CSRMap(width, gran, name)` is the declarative front-end. `RegisterSpec` plus
`bitfield`/`bitfield_set` cover simple bitfield work. A per-bus slave wrapper
maps its handshake/strobes onto the engine; the engine itself never mentions a
bus.

## `bfm` — bus-functional-model base classes

`BFMBase` is address-mapped; a per-bus BFM implements:

- `drive(addr, we, data, sel)` — drive the request signals,
- `wait_response()` — a **generator** that waits for the response and sets
  `last_data`/`last_latency`/`last_status`, and
- `release()` — deassert (optional).

The base provides `read`/`write`/`rmw` and the common `access()` template, and
emits records to `Trace`. `StreamBFMBase` is the packet/stream analogue
(`drive_beat`, `wait_beat`, `send`, `send_packet`, `recv`, `recv_packet`).
Both are simulation-only.

## `adapter` — cross-bus translators

`AdapterBase` declares `to_downstream`/`to_upstream`, the `build()` elaboration
hook, `convert_request()`/`convert_response()` translation hooks, and a common
`self_check(bfm, pairs)` loopback template that writes/reads each pair and
raises `BusProtocolError` on a mismatch.

---

## Convertibility

All synthesizable blocks (`address_decoder`, the arbiters, `RegisterEngine`)
convert to **Verilog and VHDL** and are smoke-tested (conversion + cosim +
Yosys synth). The reusable elaboration-time selection/arbitration/fanout
primitives live in `bus_common/muxing.py`. BFMs, hooks and simulation checks are
simulation-only and are never converted.
