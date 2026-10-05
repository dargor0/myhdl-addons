# `myhdl_addons.axi`

An AXI4 / AXI4-Lite / AXI4-Stream library built on the protocol-agnostic
`myhdl_addons.bus_common` layer: a multi-master / multi-slave container,
pluggable interconnect strategies (point-to-point, shared bus, crossbar),
AXI4 and AXI4-Lite master cores, a memory-backed AXI4 slave, a declarative
AXI4-Lite CSR peripheral, AXI4-Stream source/sink and utility blocks, plus
simulation BFMs and protocol checks.

The synthesizable blocks convert to **Verilog and VHDL**; the decoder, arbiter
and CSR engine are reused from `bus_common` (and, through it, the independent
`components`).

```python
from myhdl_addons.axi import (
    Axi,
    AxiPointToPoint,
    AxiSharedBus,
    AxiCrossbar,
    axi_master,
    axi_lite_master,
    axi_full_slave,
    axi_full_slave_oo,
    AxiLiteCSR,
    axis_source,
    axis_sink,
    AxiBFM,
    AxiLiteBFM,
)
```

---

## Quick start

```python
from myhdl import Signal, block, intbv
from myhdl_addons.axi import Axi, AxiPointToPoint, axi_lite_master, AxiLiteCSR


@block
def soc(aclk, aresetn):
    # 1. the bus container (geometry + interconnect strategy)
    bus = Axi(
        aclk,
        aresetn,
        data_width=32,
        addr_width=16,
        variant="lite",
        interconnect=AxiPointToPoint(),
    )

    # 2. ports: one master, one slave with an address window
    m = bus.add_master("cpu")
    s = bus.add_slave(base=0x0000, size=0x100, name="csr")

    # 3. an AXI4-Lite master core driven by a simple command interface
    start = Signal(bool(0))
    write = Signal(bool(0))
    addr = Signal(intbv(0)[16:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    busy = Signal(bool(0))
    done = Signal(bool(0))
    rdata = Signal(intbv(0)[32:])
    resp = Signal(intbv(0)[2:])
    cpu = axi_lite_master(m, start, write, addr, wdata, wstrb, busy, done, rdata, resp)

    # 4. a CSR peripheral mapped onto the slave port
    csr = AxiLiteCSR(width=32)
    csr.add_write(0x00, "CTRL")
    csr.add_ro(0x04, "ID", init=0xC0DE)
    peripheral = csr.build(s)

    # 5. elaborate the fabric
    fabric = bus.build()

    return cpu, peripheral, fabric
```

`bus.build()` returns a block to be returned from your top-level `@block`
together with the attached peripherals.

---

## What's here

| Module | Public API | Purpose |
|---|---|---|
| `interface` | `Axi`, `AxiPort`, `AxiSlavePort`, `AxiMasterView`, `AxiSlaveView` | The bus container plus raw ports and directional views. |
| `interconnect` | `AxiPointToPoint`, `AxiSharedBus`, `AxiCrossbar`, `AxiInterconnectBase`, `AxiContext` | Pluggable interconnect strategies. |
| `full` | `axi_master`, `axi_full_slave` | AXI4 master core and memory-backed slave (INCR/FIXED/WRAP). |
| `oo` | `axi_full_slave_oo` | Memory-backed AXI4 slave with outstanding reads. |
| `lite` | `axi_lite_master` | Single-beat AXI4-Lite master core. |
| `regfile` | `AxiLiteCSR`, `RegisterSpec`, `bitfield`, `bitfield_set` | Declarative CSR peripheral over the shared register engine. |
| `stream` | `axis_source`, `axis_sink` (+ sideband helpers) | AXI4-Stream source/sink adapters. |
| `stream_utils` | `axis_register_slice`, `axis_gate`, `axis_periodic_gate`, `axis_width_down`, `axis_width_up`, `axis_packet_counter` | Stream pipeline helpers. |
| `bfm` | `AxiBFM`, `AxiLiteBFM` | Simulation-only master BFMs. |
| `refmodel` | `AxiMemModel` | Simulation-only memory reference model. |
| `protocol` | `check_burst`, `check_id_unique`, `check_last_alignment`, `check_no_contention`, `check_valid_stable` | Simulation-only protocol monitors. |
| `status` | `AxiStatus`, `resp_to_status`, `status_to_resp` | Response-code mapping. |
| `trace` | `Trace`, `TransactionRecord`, `ErrorEvent`, `ContentionEvent` | Simulation-only hook registry. |
| `checks` | `AxiConfigError`, `AxiTypeError`, `AxiProtocolError`, `AxiError` | Elaboration-time validation. |

---

## The `Axi` container

```python
bus = Axi(
    aclk,
    aresetn,  # externally provided clock and active-low reset
    data_width=32,
    addr_width=32,
    id_width=4,
    user_width=0,
    variant="full",  # "full" | "lite" | "stream"
    user=False,  # enable optional user sidebands (full/stream)
    interconnect=AxiPointToPoint(),  # required before build()
    trace=False,
)
m = bus.add_master("cpu")  # -> AxiMasterView
s = bus.add_slave(base=0x0000, size=0x100, name="mem")  # -> AxiSlaveView
fabric = bus.build()  # @block: fabric + trace monitors
```

- `variant` selects the signal set: `full` (AXI4), `lite` (AXI4-Lite) or
  `stream` (AXI4-Stream).
- `add_master` / `add_slave` must be called before `build()` (later calls raise).
- `user=True` adds the optional sidebands (requires `user_width > 0`).
- `bus.trace` is the `Trace` hook registry; `bus.address_map` the `AddressMap`.

## Interconnect strategies

```python
AxiPointToPoint()  # exactly one master <-> one slave
AxiSharedBus()  # N masters arbitrated onto M decoded slaves
AxiCrossbar()  # full mesh: concurrent master/slave pairs, per-slave arbitration
```

For the `full` variant the shared bus and crossbar **remap IDs**: the granted
master index is presented as `AWID`/`ARID` to the slave and the master's
original ID is restored on `B`/`R`. A custom strategy subclasses
`AxiInterconnectBase` and implements `build(ctx)`.

## Master / slave cores

```python
axi_master(
    port,
    start,
    write,
    addr,
    length,
    wdata,
    wstrb,
    wvalid,
    wready,
    rdata,
    rvalid,
    rready,
    busy,
    done,
    burst=None,
)
axi_lite_master(port, start, write, addr, wdata, wstrb, busy, done, rdata, resp)
axi_full_slave(slave_view)
axi_full_slave_oo(slave_view, depth=4)
```

- `axi_master` supports INCR/FIXED/WRAP bursts; write beats come from an
  upstream `wdata`/`wstrb`/`wvalid` source, read beats are pushed to
  `rdata`/`rvalid`/`rready`.
- `axi_full_slave` accepts the write address before the write data (a
  protocol-legal ordering) and serializes AW/AR.
- `axi_full_slave_oo` queues up to `depth` outstanding read requests and returns
  them in order.

## CSR peripheral — `AxiLiteCSR`

```python
from myhdl_addons.axi import AxiLiteCSR

csr = AxiLiteCSR(width=32)
csr.add_write(0x00, "CTRL")  # stored, writable
csr.add_ro(0x04, "ID", init=0xC0DE)  # stored, read-only
csr.add_read(0x08, "STATUS")  # peripheral drives csr.signals["STATUS"]
peri = csr.build(slave_view)  # @block
```

The AXI4-Lite FSM maps the channel handshake onto the shared
`bus_common.RegisterEngine`; after `build`, `csr.signals[name]`, `csr.wr[name]`
and `csr.rd[name]` expose the stored signals and per-register strobes.

## AXI4-Stream

```python
src = axis_source(master_port, data, valid, last, ready)
snk = axis_sink(slave_port, ready, data, valid, last)
slice = axis_register_slice(clk, resetn, din, vin, lin, rin, dout, vout, lout, rout)
down = axis_width_down(clk, resetn, din, vin, lin, rin, dout, vout, lout, rout)
up = axis_width_up(clk, resetn, din, vin, lin, rin, dout, vout, lout, rout)
```

Source/sink adapt the simple `data`/`valid`/`last`/`ready` convention to a
stream port; the utility blocks add pipelining, gating and width conversion.
Optional sidebands (`tstrb`/`tkeep`/`tid`/`tdest`/`tuser`) are passed through by
`axis_source_sidebands` / `axis_sink_sidebands` when the port enables them.

## Simulation BFMs and tracing

```python
bfm = AxiBFM(master_view, timeout=1000)
bfm_lite = AxiLiteBFM(master_view)


@instance
def stim():
    yield bfm.write(0x00, [0x1111, 0x2222, 0x3333])
    yield bfm.read(0x00, 3)
    assert bfm.last_data == [0x1111, 0x2222, 0x3333]
```

`AxiBFM` / `AxiLiteBFM` drive a master view; results land in `last_data` /
`last_resp`. `Trace` is simulation-only and adds nothing when disabled.

---

## Convertibility

All synthesizable blocks (`axi_master`, `axi_full_slave`, `axi_full_slave_oo`,
`axi_lite_master`, `AxiLiteCSR`, the stream source/sink and utilities, and
`AxiPointToPoint` / `AxiSharedBus` / `AxiCrossbar`) convert to Verilog and VHDL
and are smoke-tested (conversion + cosim + Yosys synth). `AxiBFM` / `AxiLiteBFM`,
`AxiMemModel`, `protocol` and `Trace` are simulation-only and are never
converted.
