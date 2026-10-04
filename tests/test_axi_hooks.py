"""AXI simulation/debug hooks: response/error + contention (AX-FR-132/134)."""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import (
    Axi,
    AxiLiteBFM,
    AxiLiteCSR,
    AxiProtocolError,
    AxiSharedBus,
    Trace,
    check_id_unique,
    check_no_contention,
    check_valid_stable,
)


@block
def _protocol_tb(trace):
    clk = Signal(bool(0))
    rst = Signal(bool(1))
    valid = Signal(bool(0))
    ready = Signal(bool(0))
    data = Signal(intbv(0)[8:])

    mon = check_valid_stable(
        clk, rst, valid, ready, [data], label="aw", trace=trace, port="m0"
    )

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 0
        yield clk.posedge
        yield clk.posedge
        rst.next = 1
        valid.next = 1
        data.next = 1
        yield clk.posedge
        data.next = 2  # payload changed while waiting for READY

    @instance
    def stopper():
        yield delay(1000)
        raise StopSimulation

    return clkgen, mon, stim, stopper


def test_protocol_violation_emits_error_event():
    trace = Trace(enabled=True)
    errors = []
    trace.error(errors.append)
    with pytest.raises(AxiProtocolError):
        _protocol_tb(trace).run_sim()
    assert errors and errors[0].kind == "protocol"
    assert errors[0].port == "m0"


@block
def _checkers_tb(trace, mode, raise_on=False):
    clk = Signal(bool(0))
    rst = Signal(bool(1))
    g0 = Signal(bool(0))
    g1 = Signal(bool(0))
    v0 = Signal(bool(0))
    v1 = Signal(bool(0))
    id0 = Signal(intbv(0)[4:])
    id1 = Signal(intbv(0)[4:])

    mon_c = check_no_contention(
        clk,
        rst,
        [g0, g1],
        label="slave0",
        port="s0",
        trace=trace,
        raise_on_error=raise_on,
    )
    mon_i = check_id_unique(
        clk,
        rst,
        [v0, v1],
        [id0, id1],
        label="slave0",
        port="s0",
        trace=trace,
        raise_on_error=raise_on,
    )

    @always(delay(5))
    def clkgen():
        clk.next = not clk

    @instance
    def stim():
        rst.next = 0
        yield clk.posedge
        yield clk.posedge
        rst.next = 1
        if mode == "grant":
            g0.next = 1
            g1.next = 1
        elif mode == "id":
            v0.next = 1
            v1.next = 1
            id0.next = 3
            id1.next = 3
        else:
            g0.next = 1  # exactly one grant, no collision
        yield clk.posedge
        yield clk.posedge
        raise StopSimulation

    return clkgen, mon_c, mon_i, stim


def test_overlapping_grants_emit_contention():
    trace = Trace(enabled=True)
    got = []
    trace.contention(got.append)
    _checkers_tb(trace, "grant").run_sim()
    assert any("concurrent grants" in event.detail for event in got)


def test_id_collision_emits_contention():
    trace = Trace(enabled=True)
    got = []
    trace.contention(got.append)
    _checkers_tb(trace, "id").run_sim()
    assert any("ID collision" in event.detail for event in got)


def test_no_contention_when_exclusive():
    trace = Trace(enabled=True)
    got = []
    trace.contention(got.append)
    _checkers_tb(trace, "ok").run_sim()
    assert got == []


def test_contention_can_raise():
    with pytest.raises(AxiProtocolError):
        _checkers_tb(Trace(enabled=True), "grant", raise_on=True).run_sim()


def test_contention_without_trace_is_inert():
    # exercises the "no trace" branch of the reporters
    _checkers_tb(None, "grant").run_sim()


def test_trace_captures_transactions_and_errors():
    seen = []
    errors = []
    contended = []

    @block
    def tb():
        aclk = Signal(bool(0))
        aresetn = Signal(bool(0))

        bus = Axi(
            aclk,
            aresetn,
            data_width=32,
            addr_width=16,
            variant="lite",
            interconnect=AxiSharedBus(),
            trace=True,
        )
        m0 = bus.add_master("m0")
        s0 = bus.add_slave(base=0x0000, size=0x0100, name="s0")

        csr = AxiLiteCSR(width=32)
        csr.add_ro(0x04, "ID", init=0xC0DE)
        peri = csr.build(s0)

        bfm = AxiLiteBFM(m0, trace=bus.trace, timeout=200)
        bus.trace.transaction(seen.append)
        bus.trace.error(errors.append)
        bus.trace.contention(contended.append)
        glue = bus.build()

        @always(delay(5))
        def clkgen():
            aclk.next = not aclk

        @instance
        def stim():
            aresetn.next = 0
            yield aclk.posedge
            yield aclk.posedge
            aresetn.next = 1

            yield bfm.read(0x0004)
            assert bfm.last_data == 0xC0DE
            yield bfm.read(0x8000)  # unmapped -> default slave DECERR
            assert bfm.last_resp.value == "decerr"

            raise StopSimulation

        return clkgen, glue, peri, stim

    tb().run_sim()
    assert len(seen) >= 2
    assert errors and errors[-1].kind == "decerr"
    assert contended == []
