# `myhdl_addons.wishbone`

A Wishbone B4 (classic) bus library built on the protocol-agnostic
`myhdl_addons.bus_common` layer: a multi-master / multi-slave bus container,
pluggable interconnect strategies, a classic master core and slave helper, a
declarative CSR peripheral, and a simulation BFM.

The synthesizable blocks (`address_decoder`, the arbiter, the master/slave
helpers, the interconnect and the CSR peripheral) convert to **Verilog and
VHDL**; the decoder and arbiter reuse the shared `bus_common` (and, through it,
the independent `components`) implementations.

```python
from myhdl_addons.wishbone import (
    Wishbone,
    PointToPoint,
    SharedBus,
    Crossbar,
    wishbone_master,
    wishbone_slave,
    CSRMap,
    WishboneBFM,
)
```

---

## Quick start

```python
from myhdl import Signal, block, intbv
from myhdl_addons.wishbone import (
    Wishbone,
    PointToPoint,
    wishbone_master,
    CSRMap,
)


@block
def soc(clk, rst):
    # 1. the bus container (geometry + interconnect strategy)
    bus = Wishbone(clk, rst, data_width=32, adr_width=16, interconnect=PointToPoint())

    # 2. ports: one master, one slave with an address window
    m = bus.add_master("cpu")
    s = bus.add_slave(base=0x0000, size=0x100, name="csr")

    # 3. a classic master core driven by a simple command interface
    req = Signal(bool(0))
    adr = Signal(intbv(0)[16:])
    we = Signal(bool(0))
    dat_w = Signal(intbv(0)[32:])
    sel = Signal(intbv(0)[4:])
    busy = Signal(bool(0))
    done = Signal(bool(0))
    dat_r = Signal(intbv(0)[32:])
    err = Signal(bool(0))
    cpu = wishbone_master(m, req, adr, we, dat_w, sel, busy, done, dat_r, err)

    # 4. a CSR peripheral mapped onto the slave port
    csr = CSRMap(width=32)
    csr.add_write(0x00, "CTRL", init=0)
    csr.add_ro(0x04, "ID", init=0xCAFE)
    peripheral = csr.build(s)

    # 5. elaborate the fabric (returns the fabric + trace-monitor blocks)
    fabric = bus.build()

    return cpu, peripheral, fabric
```

`bus.build()` returns a block to be returned from your top-level `@block`
together with the attached peripherals.

---

## What's here

| Module | Public API | Purpose |
|---|---|---|
| `interface` | `Wishbone`, `MasterPort`, `MasterView`, `SlavePort`, `SlaveView` | The bus container plus raw ports and directional views. |
| `interconnect` | `PointToPoint`, `SharedBus`, `Crossbar`, `InterconnectBase`, `InterconnectContext` | Pluggable interconnect strategies. |
| `master` | `wishbone_master` | Classic Wishbone master core (simple command interface). |
| `slave` | `wishbone_slave` | Zero-wait-state classic slave helper. |
| `decoder` | `AddressMap`, `address_decoder` | Address windows and the decoder (reuses `bus_common`). |
| `arbiter` | `ArbiterBase`, `FixedPriorityArbiter`, `fixed_priority_arbiter` | Request/grant arbitration (reuses `bus_common`). |
| `regfile` | `CSRMap`, `READ`, `WRITE`, `RO` | Declarative CSR peripheral over the shared register engine. |
| `bfm` | `WishboneBFM` | Simulation-only master BFM (`read`/`write`/`rmw`). |
| `trace` | `Trace`, `TransactionRecord`, `ErrorEvent`, `ContentionEvent` | Simulation-only hook registry. |
| `checks` | `WishboneConfigError`, `WishboneTypeError`, `check_*` | Elaboration-time validation. |

---

## The `Wishbone` container

```python
bus = Wishbone(
    clk,
    rst,  # externally provided clock/reset (mandatory)
    data_width=32,
    adr_width=16,
    gran=8,
    err=False,
    rty=False,
    lock=False,  # optional Wishbone signals
    interconnect=PointToPoint(),  # default: SharedBus
    trace=False,
)
m = bus.add_master("cpu")  # -> MasterView
s = bus.add_slave(base=0x0000, size=0x100, name="csr")  # -> SlaveView
fabric = bus.build()  # @block: fabric + trace monitors
```

- `add_master` / `add_slave` must be called before `build()` (later calls raise).
- `sel_width` is derived as `data_width // gran`.
- `bus.trace` is the `Trace` hook registry.

### Port signals (`MasterView` / `SlaveView`)

| Direction | MasterView | SlaveView |
|---|---|---|
| driven by the master | `cyc_o`, `stb_o`, `we_o`, `adr_o`, `dat_o`, `sel_o`, `lock_o` | — |
| sampled by the master | `ack_i`, `dat_i`, `err_i`, `rty_i` | — |
| sampled by the slave | — | `cyc_i`, `stb_i`, `we_i`, `adr_i`, `dat_i`, `sel_i`, `lock_i` |
| driven by the slave | — | `ack_o`, `dat_o`, `err_o`, `rty_o` |

`err_i`/`rty_i`/`lock_o` (and the `_o`/`_i` counterparts) are `None` unless the
bus enabled them. `SlaveView` also exposes `base`/`size`.

## Interconnect strategies

```python
PointToPoint()  # exactly one master <-> one slave
SharedBus()  # N masters arbitrated onto M decoded slaves (default)
SharedBus(arbiter=...)  # choose the arbiter strategy
Crossbar()  # reserved (not implemented)
```

A custom strategy subclasses `InterconnectBase` and implements
`build(ctx)`, where `ctx` is an `InterconnectContext` carrying the ports,
geometry, clock/reset and the optional-signal flags:

```python
class MyFabric(InterconnectBase):
    name = "my_fabric"

    @block
    def build(self, ctx: InterconnectContext):
        ...
        return [instances]
```

## Master core — `wishbone_master`

```python
wishbone_master(wb, req, adr, we, dat_w, sel, busy, done, dat_r, err)
```

- `req` is sampled while `busy` is low; a transaction starts on the next edge.
- `done` is a one-cycle pulse; `dat_r`/`err` are valid with `done`.
- Optional `ERR`/`RTY` handling is selected at elaboration from the port's
  optional signals (a `RTY` keeps the cycle active; an `ERR` completes it with
  `err=1`).

## Slave helper — `wishbone_slave`

```python
wishbone_slave(wb, read_data, wr, rd, wr_data, wr_sel)
```

Zero-wait-state: `ack_o = cyc_i and stb_i`; `wr`/`rd` are combinational strobes;
the peripheral drives `read_data`. For memory-mapped registers prefer `CSRMap`.

## CSR peripheral — `CSRMap`

```python
from myhdl_addons.wishbone import CSRMap

csr = CSRMap(width=32)
csr.add_write(0x00, "CTRL", init=0)  # stored, writable
csr.add_ro(0x04, "ID", init=0xCAFE)  # stored, read-only
csr.add_read(0x08, "STATUS")  # peripheral drives csr.signals["STATUS"]
peri = csr.build(slave_view)  # @block
```

- Offsets are `width/8`-byte aligned; duplicate offsets/names raise.
- After `build`, `csr.signals[name]`, `csr.wr[name]` and `csr.rd[name]` expose
  the stored signal and the per-register read/write strobes (driven by the
  peripheral).

## Simulation BFM — `WishboneBFM`

```python
bfm = WishboneBFM(master_view, timeout=1000, trace=bus.trace)


@instance
def stim():
    yield bfm.write(0x00, 0xABCD)
    yield bfm.write(0x04, 0x1234)
    yield bfm.read(0x00)
    assert bfm.last_data == 0xABCD
    yield bfm.rmw(0x04, mask=0x0F, data=0x3)
```

`read`/`write`/`rmw` are generators to `yield`; read results land in
`bfm.last_data`. Errors/timeouts raise `WishboneError`.

## Tracing

```python
bus = Wishbone(clk, rst, trace=True)
bus.trace.transaction(lambda rec: print(rec.as_dict()))
bus.trace.error(lambda ev: print(ev.kind, hex(ev.address)))
bus.trace.signal(m.cyc_o, name="cyc", callback=lambda n, o, v, t: ...)
```

`Trace` is simulation-only and adds nothing when disabled.

---

## Convertibility

The synthesizable blocks convert to Verilog and VHDL:

- `address_decoder` reuses `bus_common.AddressDecoder` (via
  `bus_common.address_decoder`); the arbiter reuses
  `bus_common.fixed_priority_arbiter`.
- `wishbone_master` / `wishbone_slave` select their optional `ERR`/`RTY`
  handling at elaboration, so each FSM body stays in the convertible subset.
- The optional `ERR`/`RTY`/`LOCK` paths of `PointToPoint` and `SharedBus` each
  become their own process, created only when enabled.
- `WishboneBFM` and `Trace` are simulation-only and are never converted.
