"""``FetchUnit`` streaming, straddle, wait-state and flush tests.

The unit fetches little-endian words from a behavioural memory model with a
configurable latency, assembles 16/32-bit instructions and exposes them through
the constant decoder interface.  Depth 0/1/2 must produce an identical
instruction stream (``RC-FR-043``).
"""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.common.errors import HdlConfigError
from myhdl_addons.riscv import FetchUnit

_WORD_MASK = 0xFFFFFFFF


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


def _program():
    """Mixed 16/32-bit program with a straddling 32-bit instruction at 0x06."""
    return {
        0x00: 0x0093,
        0x02: 0x0000,
        0x04: 0x4501,
        0x06: 0x0013,
        0x08: 0xABCD,
        0x0A: 0x8082,
        0x0C: 0x0013,
        0x0E: 0x0000,
        0x10: 0x0001,
        0x12: 0x0051,
    }


def _read_word(parcels, addr):
    lo = parcels.get(addr, 0)
    hi = parcels.get(addr + 2, 0)
    return ((hi << 16) | lo) & _WORD_MASK


def _reference(parcels, start, n):
    pc = start
    out = []
    for _ in range(n):
        lo = parcels.get(pc, 0)
        if lo & 3 == 3:
            hi = parcels.get(pc + 2, 0)
            out.append((pc, (hi << 16) | lo, 0))
            pc += 4
        else:
            out.append((pc, lo, 1))
            pc += 2
    return out


@block
def _mem_model(ports, parcels, latency, error_addrs):
    """A one-outstanding-request memory with a fixed response latency."""
    pending = [None] * latency

    @instance
    def model():
        while True:
            addr = pending.pop(0)
            if addr is None:
                ports.mem_resp_valid.next = 0
                ports.mem_resp_rdata.next = 0
                ports.mem_resp_error.next = 0
            else:
                ports.mem_resp_valid.next = 1
                ports.mem_resp_rdata.next = _read_word(parcels, addr)
                ports.mem_resp_error.next = 1 if addr in error_addrs else 0
            pending.append(int(ports.mem_req_addr) if ports.mem_req_valid else None)
            yield ports.clk.posedge

    return model


def _snapshot(ports):
    return (
        int(ports.instr_pc),
        int(ports.instr_data),
        int(ports.instr_compressed),
    )


@block
def _fetch_tb(
    make_device,
    results,
    comp,
    parcels,
    n,
    latency,
    error_addrs,
    split,
    redirect,
):
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def monitor():
        # The monitor owns the handshake: sample one instruction, then consume
        # it with ``take`` before sampling again, so each instruction is
        # recorded exactly once at every buffer depth.
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        yield ports.clk.posedge
        cycles = 0
        flushed = False
        while len(results) < n and cycles < 6000:
            cycles += 1
            yield ports.clk.posedge
            yield delay(2)
            if not ports.instr_valid:
                continue
            results.append(_snapshot(ports))
            if split is not None and not flushed and len(results) == split:
                flushed = True
                ports.flush.next = 1
                ports.req_pc.next = redirect
                yield ports.clk.posedge
                ports.flush.next = 0
            else:
                ports.take.next = 1
                yield ports.clk.posedge
                ports.take.next = 0
        raise StopSimulation

    return (
        clkgen,
        dut,
        _mem_model(ports, parcels, latency, error_addrs),
        monitor,
    )


def _run(make_device, comp, parcels, n, **kwargs):
    options = {
        "latency": 1,
        "error_addrs": (),
        "split": None,
        "redirect": None,
    }
    options.update(kwargs)
    results = []
    _fetch_tb(make_device, results, comp, parcels, n, **options).run_sim()
    return results


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_depth_matrix(depth):
    comp = FetchUnit(fetch_buffer=depth, reset_vector=0)
    got = _run(_python_device, comp, _program(), 8)
    assert got == _reference(_program(), 0, 8)


@pytest.mark.parametrize("depth", [0, 1, 2])
@pytest.mark.parametrize("latency", [1, 2, 4])
def test_fetch_straddle_across_waits(depth, latency):
    comp = FetchUnit(fetch_buffer=depth, reset_vector=0)
    got = _run(_python_device, comp, _program(), 8, latency=latency)
    expected = _reference(_program(), 0, 8)
    assert got == expected
    # the straddling 32-bit instruction at 0x06 must be assembled correctly
    assert (0x06, 0xABCD0013, 0) in got


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_start_offset_two(depth):
    # first instruction itself straddles the word (starts at offset 2)
    parcels = {0x02: 0x0013, 0x04: 0xBEEF, 0x06: 0x0001}
    comp = FetchUnit(fetch_buffer=depth, reset_vector=0x02)
    got = _run(_python_device, comp, parcels, 2, latency=2)
    assert got == _reference(parcels, 0x02, 2)
    assert got[0] == (0x02, 0xBEEF0013, 0)


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_streams_long_run(depth):
    parcels = {addr: 0x0001 for addr in range(0, 0x100, 2)}
    comp = FetchUnit(fetch_buffer=depth, reset_vector=0)
    got = _run(_python_device, comp, parcels, 40, latency=1)
    assert got == _reference(parcels, 0, 40)


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_fetch_flush_redirect(depth):
    comp = FetchUnit(fetch_buffer=depth, reset_vector=0)
    got = _run(_python_device, comp, _program(), 6, split=3, redirect=0x0A)
    expected = _reference(_program(), 0, 3) + _reference(_program(), 0x0A, 3)
    assert got == expected


@block
def _stall_tb(make_device, out, comp, parcels):
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
        yield delay(1)
        while not ports.instr_valid:
            yield ports.clk.posedge
            yield delay(1)
        for _ in range(4):
            out.append(_snapshot(ports))
            yield ports.clk.posedge
            yield delay(1)
        ports.take.next = 1
        yield ports.clk.posedge
        ports.take.next = 0
        yield delay(1)
        out.append(_snapshot(ports))
        raise StopSimulation

    return clkgen, dut, _mem_model(ports, parcels, 1, ()), stim


def test_fetch_stall_holds_instruction():
    comp = FetchUnit(fetch_buffer=1, reset_vector=0)
    out = []
    _stall_tb(_python_device, out, comp, _program()).run_sim()
    assert len(set(out[:4])) == 1  # valid/data/pc stable while !take
    assert out[0][0] == 0
    assert out[4][0] == 4  # advanced by 4 after take


@block
def _flush_probe_tb(make_device, out, comp, redirect):
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
        ports.flush.next = 1
        ports.req_pc.next = redirect
        yield ports.clk.posedge
        ports.flush.next = 0
        yield delay(1)
        out.append((int(ports.misaligned), int(ports.instr_pc)))
        raise StopSimulation

    return clkgen, dut, _mem_model(ports, _program(), 1, ()), stim


def test_fetch_misaligned_target():
    comp = FetchUnit(fetch_buffer=1, reset_vector=0)
    out = []
    _flush_probe_tb(_python_device, out, comp, 0x05).run_sim()
    assert out == [(1, 0x05)]


@block
def _error_tb(make_device, out, comp, error_addr):
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
        for _ in range(6):
            yield ports.clk.posedge
        yield delay(1)
        out.append((int(ports.fault), int(ports.instr_valid)))
        raise StopSimulation

    return clkgen, dut, _mem_model(ports, {}, 1, (error_addr,)), stim


def test_fetch_fault_on_bus_error():
    comp = FetchUnit(fetch_buffer=1, reset_vector=0)
    out = []
    _error_tb(_python_device, out, comp, 0).run_sim()
    assert out == [(1, 0)]


def test_fetch_parameters_and_validation():
    comp = FetchUnit(fetch_buffer=2, reset_vector=0x100)
    assert comp.as_dict()["fetch_buffer"] == 2
    assert comp.as_dict()["reset_vector"] == 0x100
    assert "FetchUnit" in repr(comp)
    with pytest.raises(HdlConfigError):
        FetchUnit(fetch_buffer=3)
    with pytest.raises(HdlConfigError):
        FetchUnit(reset_vector=3)
