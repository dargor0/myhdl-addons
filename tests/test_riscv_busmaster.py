"""``BusMaster`` Wishbone transaction and arbitration tests.

A behavioural Wishbone slave (flat ``wb_*`` ports) backs the adapter; two Q31
clients (``c0`` fetch / ``c1`` data) are driven sequentially or concurrently.
"""

import pytest
from myhdl import (
    Signal,
    StopSimulation,
    always,
    always_comb,
    block,
    delay,
    instance,
    intbv,
)

from test_riscv_router import _align

from myhdl_addons.common.errors import HdlConfigError
from myhdl_addons.riscv import BusMaster


class _Mem:
    def __init__(self, init, err_addrs=()):
        self.words = dict(init)
        self.err_addrs = set(err_addrs)

    def read_word(self, addr):
        return self.words.get(addr & ~3, 0)

    def write(self, addr, dat_w, sel):
        word_addr = addr & ~3
        word = self.words.get(word_addr, 0)
        for lane in range(4):
            if (sel >> lane) & 1:
                byte = (dat_w >> (8 * lane)) & 0xFF
                word = (word & ~(0xFF << (8 * lane))) | (byte << (8 * lane))
        self.words[word_addr] = word


@block
def _slave(ports, mem):
    @always_comb
    def comb():
        active = ports.wb_cyc and ports.wb_stb
        ports.wb_ack.next = active
        if active and (int(ports.wb_adr) in mem.err_addrs):
            ports.wb_err.next = 1
        else:
            ports.wb_err.next = 0
        ports.wb_dat_r.next = mem.read_word(int(ports.wb_adr))

    @instance
    def wr():
        while True:
            yield ports.clk.posedge
            if ports.wb_cyc and ports.wb_stb and ports.wb_we:
                mem.write(int(ports.wb_adr), int(ports.wb_dat_w), int(ports.wb_sel))

    return comb, wr


@block
def _slow_slave(ports, mem, wait):
    """A slave that asserts ``ack`` only after *wait* wait-states."""

    count = Signal(intbv(0, min=0, max=wait + 1))

    @always(ports.clk.posedge)
    def fsm():
        if ports.wb_cyc and ports.wb_stb:
            if count == wait:
                count.next = 0
            else:
                count.next = count + 1
        else:
            count.next = 0

    @always_comb
    def comb():
        active = ports.wb_cyc and ports.wb_stb and (count == wait)
        ports.wb_ack.next = active
        if active and (int(ports.wb_adr) in mem.err_addrs):
            ports.wb_err.next = 1
        else:
            ports.wb_err.next = 0
        ports.wb_dat_r.next = mem.read_word(int(ports.wb_adr))

    @instance
    def wr():
        while True:
            yield ports.clk.posedge
            if ports.wb_cyc and ports.wb_stb and ports.wb_we and (count == wait):
                mem.write(int(ports.wb_adr), int(ports.wb_dat_w), int(ports.wb_sel))

    return fsm, comb, wr


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


def _mem():
    return _Mem({0x00: 0x11111111, 0x04: 0x22222222, 0x08: 0x33333333})


@block
def _bus_tb(make_device, results, comp, ops, mem, wait=0):
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
        yield ports.clk.posedge
        for op in ops:
            client = op["client"]
            getattr(ports, f"{client}_req_addr").next = op["addr"]
            if client == "c1":
                we = op.get("we", 0)
                ports.c1_req_we.next = we
                if we:
                    aligned, strobes = _align(
                        op["addr"], op.get("size", 0), op.get("wdata", 0)
                    )
                    ports.c1_req_wdata.next = aligned
                    ports.c1_req_wstrb.next = strobes
                else:
                    ports.c1_req_wdata.next = 0
                    ports.c1_req_wstrb.next = 0b1111
            getattr(ports, f"{client}_req_valid").next = 1
            yield delay(1)
            guard = 0
            while not getattr(ports, f"{client}_resp_valid"):
                yield ports.clk.posedge
                yield delay(1)
                guard += 1
                assert guard < 100
            results.append(
                (
                    int(getattr(ports, f"{client}_resp_rdata")),
                    int(getattr(ports, f"{client}_resp_error")),
                )
            )
            getattr(ports, f"{client}_req_valid").next = 0
            yield ports.clk.posedge
            yield delay(1)
        raise StopSimulation

    if wait:
        slave = _slow_slave(ports, mem, wait)
    else:
        slave = _slave(ports, mem)
    return clkgen, dut, slave, stim


def _run(make_device, ops, mem, comp=None, wait=0):
    comp = comp or BusMaster()
    results = []
    _bus_tb(make_device, results, comp, ops, mem, wait).run_sim()
    return results


def test_busmaster_reads_both_clients():
    ops = [
        {"client": "c0", "addr": 0x00, "size": 2},
        {"client": "c0", "addr": 0x04, "size": 2},
        {"client": "c1", "addr": 0x08, "size": 2},
        {"client": "c1", "addr": 0x00, "size": 2},
    ]
    mem = _mem()
    got = _run(_python_device, ops, mem)
    assert got == [
        (0x11111111, 0),
        (0x22222222, 0),
        (0x33333333, 0),
        (0x11111111, 0),
    ]


def test_busmaster_store_then_load():
    ops = [
        {"client": "c1", "addr": 0x10, "we": 1, "wdata": 0xCAFEBABE, "size": 2},
        {"client": "c0", "addr": 0x10, "size": 2},
        {"client": "c1", "addr": 0x11, "we": 1, "wdata": 0x5A, "size": 0},
        {"client": "c1", "addr": 0x10, "size": 2},
    ]
    mem = _mem()
    got = _run(_python_device, ops, mem)
    assert got[1] == (0xCAFEBABE, 0)
    assert got[3] == (0xCAFE5ABE, 0)
    assert all(error == 0 for _, error in got)


def test_busmaster_halfword_store():
    ops = [
        {"client": "c1", "addr": 0x12, "we": 1, "wdata": 0xBEEF, "size": 1},
        {"client": "c1", "addr": 0x10, "size": 2},
    ]
    got = _run(_python_device, ops, _mem())
    assert got[-1] == (0xBEEF0000, 0)


def test_busmaster_error_response():
    ops = [{"client": "c1", "addr": 0x20, "size": 2}]
    mem = _Mem({}, err_addrs=(0x20,))
    got = _run(_python_device, ops, mem)
    assert got == [(0, 1)]


@block
def _bus_concurrent_tb(make_device, out, comp, mem, addr0, addr1):
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
        yield ports.clk.posedge
        ports.c0_req_addr.next = addr0
        ports.c0_req_valid.next = 1
        ports.c1_req_addr.next = addr1
        ports.c1_req_wstrb.next = 0b1111
        ports.c1_req_valid.next = 1
        yield delay(1)
        guard = 0
        while not ports.c0_resp_valid:
            yield ports.clk.posedge
            yield delay(1)
            guard += 1
            assert guard < 100
        out.append((int(ports.c0_resp_rdata), int(ports.c0_resp_error)))
        ports.c0_req_valid.next = 0
        guard = 0
        while not ports.c1_resp_valid:
            yield ports.clk.posedge
            yield delay(1)
            guard += 1
            assert guard < 100
        out.append((int(ports.c1_resp_rdata), int(ports.c1_resp_error)))
        ports.c1_req_valid.next = 0
        raise StopSimulation

    return clkgen, dut, _slave(ports, mem), stim


def test_busmaster_arbitrates_concurrent_clients():
    out = []
    mem = _mem()
    _bus_concurrent_tb(_python_device, out, BusMaster(), mem, 0x04, 0x08).run_sim()
    assert out == [(0x22222222, 0), (0x33333333, 0)]


def test_busmaster_parameters_and_metadata():
    comp = BusMaster(data_width=32, adr_width=16)
    assert comp.as_dict()["width"] == 32
    assert comp.as_dict()["transport"] == "wishbone"
    assert comp.as_dict()["adr_width"] == 16
    assert "BusMaster" in repr(comp)


def test_busmaster_rejects_unavailable_transport():
    with pytest.raises(HdlConfigError):
        BusMaster(transport="axi")
    with pytest.raises(HdlConfigError):
        BusMaster(transport="pcie")


def test_busmaster_tolerates_wait_states():
    ops = [
        {"client": "c1", "addr": 0x10, "we": 1, "wdata": 0xCAFEBABE, "size": 2},
        {"client": "c0", "addr": 0x10, "size": 2},
        {"client": "c1", "addr": 0x00, "size": 2},
    ]
    got = _run(_python_device, ops, _mem(), wait=3)
    assert all(error == 0 for _, error in got)
    assert got[1] == (0xCAFEBABE, 0)
    assert got[2] == (0x11111111, 0)
