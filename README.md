myhdl-addons
============

A growing set of reusable, synthesizable digital-hardware building blocks written in MyHDL 0.11 (Python 3.10–3.14). Runtime depends only on `myhdl`, and every synthesizable block converts to Verilog and VHDL.

The aim is to compose a system-on-chip from tested library blocks instead of hand-writing RTL:

* **Basic components**: arithmetic/logic units, multipliers, muxes, registers, shifters, counters, comparators, memories, FIFOs and address decoders.
* **Bus implementations**: a protocol-agnostic bus layer plus Wishbone and AXI4 / AXI4-Lite / AXI4-Stream.
* **A RISC-V core**: RV32I + the C extension, microcontroller class (in construction).
* **Algorithm-acceleration blocks**: (in construction).

Packages (`src/myhdl_addons/`)
-----------------------------

| Package | What it is | Documentation |
|---|---|---|
| `common` | Shared foundation: unified exceptions, config validators + `ComponentBase`, `SignalView`/`connect`, reset handling. |  |
| `components` | Independent, ISA-neutral, bus-agnostic building blocks (`Alu`, `Mux`, `MuxTree`, `BarrelShifter`, `Fifo`, ...). | [`components/README.md`](src/myhdl_addons/components/README.md) |
| `bus_common` | Protocol-agnostic bus layer (ports, containers, arbiters, address map, CSR engine, BFMs, trace). | [`bus_common/README.md`](src/myhdl_addons/bus_common/README.md) |
| `wishbone` | Wishbone B4 (classic) bus library. | [`wishbone/README.md`](src/myhdl_addons/wishbone/README.md) |
| `axi` | AXI4 / AXI4-Lite / AXI4-Stream library. | [`axi/README.md`](src/myhdl_addons/axi/README.md) |
| `riscv` | RV32I + C (compressed) microcontroller-class core. | [`riscv/README.md`](src/myhdl_addons/riscv/README.md) |

Quick start — a component
-------------------------

```python
from myhdl_addons.components import Alu

alu = Alu(width=8, ops=["ADD", "SUB"], flags=["zero"])
ports = alu.ports()          # a SignalView of named signals
dut = alu.hdl(ports)         # MyHDL instances: simulate or instantiate
ports.a.next = 0x05
ports.b.next = 0x03
ports.op.next = alu.get_op_intmap()["ADD"]
```

Quick start — a bus
-------------------

```python
from myhdl import Signal, block, intbv
from myhdl_addons.wishbone import Wishbone, PointToPoint, wishbone_master, CSRMap

@block
def soc(clk, rst):
    bus = Wishbone(clk, rst, data_width=32, adr_width=16, interconnect=PointToPoint())
    m = bus.add_master("cpu")
    s = bus.add_slave(base=0x0000, size=0x100, name="csr")

    csr = CSRMap(width=32)
    csr.add_write(0x00, "CTRL")
    csr.add_ro(0x04, "ID", init=0xCAFE)

    cpu = wishbone_master(
        m,
        Signal(bool(0)), Signal(intbv(0)[16:]), Signal(bool(0)),
        Signal(intbv(0)[32:]), Signal(intbv(0)[4:]),
        Signal(bool(0)), Signal(bool(0)), Signal(intbv(0)[32:]), Signal(bool(0)),
    )
    return cpu, csr.build(s), bus.build()
```

Examples
--------

Runnable demos live under `examples/` (run any with `python examples/<name>.py`):

| Example | Shows |
|---|---|
| `components_alu.py` | Using a reusable `Alu` and converting it to Verilog + VHDL. |
| `components_multiplier.py` | Using combinational + sequential multipliers and converting them to Verilog + VHDL. |
| `wishbone_p2p_csr.py` | A BFM master driving a Wishbone CSR over a point-to-point bus. |
| `wishbone_shared_bus.py` | Two BFM masters reaching two CSR slaves over a shared bus. |
| `axi_lite_csr.py` | An AXI4-Lite BFM master driving a CSR peripheral. |
| `axi_crossbar.py` | Two AXI4-Lite masters reaching two CSR slaves over a crossbar. |
| `axi_full_burst.py` | An AXI4 INCR-burst write/read against a memory slave. |
| `axi_stream_pipeline.py` | AXI4-Stream packet source → sink. |

Testing
-------

Install the development extras and run the suite:

```
pip install -e ".[dev]"
pytest                                   # run the tests
pytest -k alu                            # a subset (pytest selector)
pytest --cov=myhdl_addons --cov-report=term-missing   # with coverage
ruff format --check src tests            # formatting
ruff check src tests                     # linting
```

Tests include conversion smoke tests (Verilog + VHDL) for every component, plus cosimulation (with Verilog only) and Yosys synthesis smoke tests for every synthesizable block.  The cosim/synth tests need an HDL toolchain (`iverilog`/`vvp` + a C compiler, and `yosys`); they skip automatically when tools are absent.
