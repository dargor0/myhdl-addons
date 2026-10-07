"""``ToHost`` interception, halt and signature (``RC-FR-111/113``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.riscv import ToHost

_TOHOST = 0x1000
_FROMHOST = 0x1004


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


@block
def _tohost_tb(make_device, results):
    comp = ToHost(tohost_addr=_TOHOST, fromhost_addr=_FROMHOST)
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1

        # interception (combinational): tohost / fromhost / neither
        ports.addr.next = _TOHOST
        yield delay(1)
        results.append(("comb", int(ports.hit), int(ports.rdata)))

        ports.addr.next = _FROMHOST
        ports.load.next = 1
        ports.fromhost_data.next = 0xCAFE
        yield delay(1)
        results.append(("comb", int(ports.hit), int(ports.rdata)))

        ports.addr.next = 0x2000
        yield delay(1)
        results.append(("comb", int(ports.hit), int(ports.rdata)))

        # store to tohost latches the signature and asserts halt
        ports.addr.next = _TOHOST
        ports.load.next = 0
        ports.store.next = 1
        ports.wdata.next = 3
        yield ports.clk.posedge
        yield delay(1)
        results.append(("edge", int(ports.halt), int(ports.signature)))

        # a store elsewhere leaves the sticky halt/signature unchanged
        ports.addr.next = 0x2000
        ports.wdata.next = 9
        yield ports.clk.posedge
        yield delay(1)
        results.append(("edge", int(ports.halt), int(ports.signature)))

        # a later fromhost load still returns host data (halt stays asserted)
        ports.addr.next = _FROMHOST
        ports.store.next = 0
        ports.load.next = 1
        ports.fromhost_data.next = 0xBEEF
        yield delay(1)
        results.append(("comb", int(ports.hit), int(ports.rdata)))

        raise StopSimulation

    return clkgen, dut, stim


def test_tohost_behaviour():
    results = []
    _tohost_tb(_python_device, results).run_sim()
    assert results == [
        ("comb", 1, 0x0000),  # tohost address, not a load
        ("comb", 1, 0xCAFE),  # fromhost load returns host input
        ("comb", 0, 0x0000),  # ordinary address
        ("edge", 1, 0x0003),  # store to tohost -> halt + signature
        ("edge", 1, 0x0003),  # store elsewhere -> unchanged
        ("comb", 1, 0xBEEF),  # host input updated
    ]


@block
def _reset_tb(results):
    comp = ToHost(tohost_addr=_TOHOST, fromhost_addr=_FROMHOST)
    ports = comp.ports()
    dut = comp.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1

        ports.addr.next = _TOHOST
        ports.store.next = 1
        ports.wdata.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.halt), int(ports.signature)))

        ports.store.next = 0
        ports.reset.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.halt), int(ports.signature)))

        raise StopSimulation

    return clkgen, dut, stim


def test_tohost_reset_clears_halt():
    results = []
    _reset_tb(results).run_sim()
    assert results == [(1, 1), (0, 0)]


def test_tohost_parameters_and_metadata():
    comp = ToHost(tohost_addr=0x8000, fromhost_addr=0x8004)
    assert comp.as_dict()["tohost_addr"] == 0x8000
    assert comp.as_dict()["fromhost_addr"] == 0x8004
    assert "ToHost" in repr(comp)


@block
def _tohost_edge_tb(make_device, results):
    comp = ToHost(tohost_addr=0x8000, fromhost_addr=0x8004)
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1

        # a store to fromhost must NOT halt
        ports.addr.next = 0x8004
        ports.store.next = 1
        ports.wdata.next = 0xDEAD
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.halt), int(ports.signature)))

        # a load from tohost is intercepted but not a fromhost load -> rdata 0
        ports.addr.next = 0x8000
        ports.store.next = 0
        ports.load.next = 1
        ports.fromhost_data.next = 0x1234
        yield delay(1)
        results.append((int(ports.hit), int(ports.rdata)))

        # a store to the (custom) tohost does halt
        ports.addr.next = 0x8000
        ports.store.next = 1
        ports.load.next = 0
        ports.wdata.next = 5
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.halt), int(ports.signature)))

        raise StopSimulation

    return clkgen, dut, stim


def test_tohost_edges_and_custom_addresses():
    results = []
    _tohost_edge_tb(_python_device, results).run_sim()
    assert results == [(0, 0), (1, 0), (1, 5)]
