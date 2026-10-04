"""Common simulation/debug hook registry (CB-FR-110..113)."""

from myhdl import Signal, StopSimulation, block, delay, instance

from myhdl_addons.bus_common.records import (
    ContentionEvent,
    ErrorEvent,
    TransactionRecord,
)
from myhdl_addons.bus_common.trace import Trace


def test_transaction_and_error_emission():
    trace = Trace(enabled=True)
    seen = []
    errors = []
    trace.transaction(seen.append)
    trace.error(errors.append)
    trace.emit_transaction(TransactionRecord(address=0x10))
    trace.emit_error(ErrorEvent(port="m0", address=0x10, kind="error"))
    assert len(seen) == 1 and seen[0].address == 0x10
    assert len(errors) == 1 and errors[0].kind == "error"


def test_port_filtering():
    trace = Trace(enabled=True)
    got = []
    trace.transaction(got.append, port="m0")
    trace.emit_transaction(TransactionRecord(port="m1"))
    assert got == []
    trace.emit_transaction(TransactionRecord(port="m0"))
    assert len(got) == 1


def test_enable_disable_by_name_and_globally():
    trace = Trace(enabled=True)
    got = []
    trace.transaction(got.append, name="tx")
    trace.disable("tx")
    trace.emit_transaction(TransactionRecord())
    assert got == []
    trace.enable("tx")
    trace.emit_transaction(TransactionRecord())
    assert len(got) == 1
    trace.disable()
    trace.emit_transaction(TransactionRecord())
    assert len(got) == 1
    trace.enable()
    trace.emit_transaction(TransactionRecord())
    assert len(got) == 2


def test_disable_signal_hook_and_unknown():
    sig = Signal(bool(0))
    trace = Trace(enabled=True)
    trace.signal(sig, name="cyc", callback=lambda *a: None)
    # exercises the signal-hook lookup branch and the not-found fallback
    trace.disable("cyc")
    trace.enable("cyc")
    trace.disable("does-not-exist")


def test_disabled_is_inert():
    trace = Trace(enabled=False)
    got = []
    trace.transaction(got.append)
    trace.emit_transaction(TransactionRecord())
    trace.emit_error(ErrorEvent())
    trace.emit_contention(ContentionEvent())
    assert got == []
    assert trace.monitors() is not None


def test_contention_emission():
    trace = Trace(enabled=True)
    got = []
    trace.contention(got.append)
    trace.emit_contention(ContentionEvent(detail="two grants"))
    assert len(got) == 1 and got[0].detail == "two grants"


@block
def _emit_tb(seen):
    trace = Trace(enabled=True)
    trace.error(lambda e: seen.append(("err", e.kind)))
    trace.contention(lambda c: seen.append(("cont", c.detail)))

    @instance
    def stim():
        yield delay(1)
        trace.emit_error(ErrorEvent(address=0x4, kind="retry"))
        trace.emit_contention(ContentionEvent(detail="grant conflict"))
        raise StopSimulation

    return stim


def test_emit_in_simulation_sets_time():
    seen = []
    _emit_tb(seen).run_sim()
    assert ("err", "retry") in seen
    assert ("cont", "grant conflict") in seen


@block
def _monitor_tb(seen):
    sig = Signal(bool(0))
    trace = Trace(enabled=True)
    trace.signal(
        sig, name="sig", callback=lambda name, old, new, tm: seen.append((name, new))
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
    assert seen
    assert seen[0][0] == "sig"
