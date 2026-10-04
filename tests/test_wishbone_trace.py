"""Simulation/debug hook tests (WB-FR-130..132, 135, 139)."""

from myhdl import Signal, StopSimulation, block, delay, instance

from myhdl_addons.wishbone import Wishbone
from myhdl_addons.wishbone.trace import (
    ContentionEvent,
    ErrorEvent,
    Trace,
    TransactionRecord,
)


def _bus(**kw):
    return Wishbone(Signal(bool(0)), Signal(bool(0)), **kw)


def test_transaction_callback():
    bus = _bus(trace=True)
    seen = []
    bus.trace.transaction(seen.append)
    bus.trace.emit_transaction(TransactionRecord(address=0x10))
    assert len(seen) == 1
    assert seen[0].address == 0x10


def test_multiple_subscribers_and_filtering():
    bus = _bus(trace=True)
    a, b = [], []
    bus.trace.transaction(a.append)
    bus.trace.transaction(b.append)
    bus.trace.signal(Signal(bool(0)), name="cyc")
    bus.trace.emit_transaction(TransactionRecord(address=0x20))
    assert len(a) == 1 and len(b) == 1
    assert len(bus.trace._signals) == 1
    assert bus.trace.monitors() is not None


def test_trace_disabled_is_inert():
    t = Trace(enabled=False)
    seen = []
    t.transaction(seen.append)
    t.emit_transaction(TransactionRecord(address=0x1))
    assert seen == []
    assert t.monitors() is not None


def test_records_and_repr():
    rec = TransactionRecord(port="m0", address=0x4, we=True, sel=0xF)
    rec.response = "ack"
    rec.latency = 3
    data = rec.as_dict()
    assert data["address"] == 0x4
    assert data["we"] is True
    assert data["latency"] == 3
    assert "m0" in repr(rec)

    err = ErrorEvent(port="m0", address=0x4, kind="err")
    assert err.kind == "err"
    cont = ContentionEvent(detail="grant conflict")
    assert cont.detail == "grant conflict"


@block
def _emit_tb(seen):
    trace = Trace(enabled=True)
    trace.error(lambda e: seen.append(("err", e.kind)))
    trace.contention(lambda c: seen.append(("cont", c.detail)))

    @instance
    def stim():
        yield delay(1)
        trace.emit_error(ErrorEvent(address=0x4, kind="rty"))
        trace.emit_contention(ContentionEvent(detail="grant conflict"))
        raise StopSimulation

    return stim


def test_emit_error_and_contention_in_simulation():
    seen = []
    _emit_tb(seen).run_sim()
    assert ("err", "rty") in seen
    assert ("cont", "grant conflict") in seen


@block
def _monitor_tb(seen):
    sig = Signal(bool(0))
    trace = Trace(enabled=True)
    trace.signal(
        sig,
        name="sig",
        callback=lambda name, old, new, tm: seen.append((name, old, new)),
    )
    watchers = trace.monitors()

    @instance
    def stim():
        yield delay(2)
        sig.next = 1
        yield delay(2)
        sig.next = 0
        yield delay(2)
        raise StopSimulation

    return watchers, stim


def test_signal_monitor_in_simulation():
    seen = []
    _monitor_tb(seen).run_sim()
    assert seen, "signal monitor never fired"
    assert seen[0][0] == "sig"
