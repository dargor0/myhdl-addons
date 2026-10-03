"""Port views and copy-wiring (``IC-FR-145..147``)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance, intbv

from myhdl_addons.components import HdlConfigError, SignalView, connect


def test_signal_view_container():
    a = Signal(intbv(0)[4:])
    view = SignalView(a=a, y=Signal(intbv(0)[4:]))
    assert view.a is a
    assert view["a"] is a
    assert "a" in view
    assert view.names == ["a", "y"]
    assert len(view) == 2
    assert list(view) == ["a", "y"]
    assert set(view.signals) == {"a", "y"}
    assert "SignalView" in repr(view)


@block
def _connect_tb(results):
    src = SignalView(a=Signal(intbv(0)[4:]), b=Signal(intbv(0)[4:]))
    dst = SignalView(a=Signal(intbv(0)[4:]), b=Signal(intbv(0)[4:]))
    wiring = connect(src, dst)

    @instance
    def stim():
        src.a.next = 5
        src.b.next = 9
        yield delay(1)
        results.append((int(dst.a), int(dst.b)))
        src.a.next = 1
        yield delay(1)
        results.append((int(dst.a),))
        raise StopSimulation

    return wiring, stim


def test_connect_copies_matching_members():
    results = []
    _connect_tb(results).run_sim()
    assert results[0] == (5, 9)
    assert results[1] == (1,)


def test_connect_no_match_raises():
    src = SignalView(a=Signal(intbv(0)[4:]))
    dst = SignalView(b=Signal(intbv(0)[4:]))
    with pytest.raises(HdlConfigError):
        connect(src, dst)


def test_view_connect_method_and_lists():
    src = SignalView(items=[Signal(intbv(0)[4:]) for _ in range(2)])
    dst = SignalView(items=[Signal(intbv(0)[4:]) for _ in range(2)])
    wiring = dst.connect(src)
    assert wiring is not None

    mismatch = SignalView(items=[Signal(intbv(0)[4:])])
    with pytest.raises(HdlConfigError):
        connect(src, mismatch)
