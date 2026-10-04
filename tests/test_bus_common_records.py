"""Common transaction/event records and enums (CB-FR-080..082)."""

from myhdl_addons.bus_common.records import (
    BusStatus,
    ContentionEvent,
    Direction,
    ErrorEvent,
    TransactionRecord,
)


def test_bus_status():
    assert BusStatus.OK.value == "ok"
    assert {s.name for s in BusStatus} == {"OK", "ERROR", "RETRY", "DENIED", "EXOKAY"}


def test_direction():
    assert Direction.READ.value == "read"
    assert {d.name for d in Direction} == {"READ", "WRITE", "ATOMIC", "STREAM"}


def test_transaction_record_serialization():
    rec = TransactionRecord(
        port="m0",
        address=0x10,
        direction=Direction.WRITE,
        length=2,
        data=5,
        extra={"burst": "incr"},
    )
    rec.latency = 3
    data = rec.as_dict()
    assert data["port"] == "m0"
    assert data["address"] == 0x10
    assert data["direction"] == "write"
    assert data["status"] == "ok"
    assert data["length"] == 2
    assert data["data"] == 5
    assert data["latency"] == 3
    assert data["extra"] == {"burst": "incr"}
    assert "m0" in repr(rec)


def test_error_event():
    event = ErrorEvent(port="s0", address=0x4, kind="retry", extra={"reason": "busy"})
    data = event.as_dict()
    assert data["kind"] == "retry"
    assert data["address"] == 0x4
    assert data["extra"] == {"reason": "busy"}
    assert data["time"] is None
    assert "s0" in repr(event)


def test_contention_event():
    event = ContentionEvent(detail="two grants", port="m1")
    data = event.as_dict()
    assert data["detail"] == "two grants"
    assert data["port"] == "m1"
    assert data["extra"] == {}
    assert "m1" in repr(event)
