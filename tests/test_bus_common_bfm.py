"""Common BFM bases (CB-FR-090..093)."""

import pytest
from myhdl import Signal, StopSimulation, block, delay, instance

from myhdl_addons.bus_common.bfm import BFMBase, StreamBFMBase
from myhdl_addons.bus_common.records import BusStatus
from myhdl_addons.bus_common.trace import Trace


class _Port:
    def __init__(self, clk):
        self.name = "m0"
        self.clk = clk


class _DummyBFM(BFMBase):
    def __init__(self, port, trace=None):
        super().__init__(port, timeout=10, trace=trace)
        self.driven = None

    def drive(self, addr, we, data, sel=None):
        self.driven = (addr, we, data)
        self._we = we

    def wait_response(self):
        yield self.port.clk.posedge
        if not self._we:
            self.last_data = 0x1234
        self.last_latency = 1

    def release(self):
        self.driven = None


class _ErrorBFM(BFMBase):
    def drive(self, addr, we, data, sel=None):
        self._we = we

    def wait_response(self):
        self.last_error = True
        self.last_status = BusStatus.ERROR
        self.last_latency = 1
        yield delay(1)


@block
def _bfm_tb(trace):
    clk = Signal(bool(0))
    bfm = _DummyBFM(_Port(clk), trace=trace)

    @instance
    def clkgen():
        while True:
            yield delay(5)
            clk.next = not clk

    @instance
    def stim():
        yield bfm.write(0x10, 0xAB)
        assert bfm.driven is None
        yield bfm.read(0x10)
        assert bfm.last_data == 0x1234
        assert bfm.last_latency == 1
        yield bfm.rmw(0x10, 0x0F, 0x05)
        assert bfm.last_data == 0x1234
        raise StopSimulation

    return clkgen, stim


def test_bfm_read_write_rmw():
    _bfm_tb(None).run_sim()


def test_bfm_trace_events():
    trace = Trace(enabled=True)
    seen = []
    trace.transaction(seen.append)
    _bfm_tb(trace).run_sim()
    assert len(seen) == 4


@block
def _error_tb(seen):
    trace = Trace(enabled=True)
    trace.error(seen.append)
    bfm = _ErrorBFM(_Port(Signal(bool(0))), trace=trace)

    @instance
    def stim():
        yield bfm.read(0x4)
        raise StopSimulation

    return stim


def test_bfm_error_emits_event():
    seen = []
    _error_tb(seen).run_sim()
    assert len(seen) == 1
    assert seen[0].kind == BusStatus.ERROR.value


def test_bfm_base_not_implemented():
    bfm = BFMBase(None)
    with pytest.raises(NotImplementedError):
        bfm.drive(0, False, 0)
    with pytest.raises(NotImplementedError):
        bfm.wait_response()
    bfm.release()
    assert bfm.port_name is None


class _DummyStream(StreamBFMBase):
    def __init__(self, rx):
        super().__init__(None)
        self.sent = []
        self.rx = list(rx)
        self._tx = False

    def drive_beat(self, data, last=False):
        self.sent.append((data, last))
        self._tx = True

    def wait_beat(self):
        if not self._tx:
            self.last_data = self.rx.pop(0)
        self._tx = False
        yield delay(1)


@block
def _stream_tb():
    stream = _DummyStream([1, 2, 3])

    @instance
    def stim():
        yield stream.send(10)
        assert stream.sent[-1] == (10, False)
        yield stream.send(11, last=True)
        assert stream.sent[-1] == (11, True)
        yield stream.send_packet([7, 8, 9])
        assert stream.sent[-1] == (9, True)
        yield stream.recv_packet(3)
        assert stream.last_data == [1, 2, 3]
        raise StopSimulation

    return stim


def test_stream_bfm_packet():
    _stream_tb().run_sim()


def test_stream_base_not_implemented():
    stream = StreamBFMBase(None)
    with pytest.raises(NotImplementedError):
        stream.drive_beat(0)
    with pytest.raises(NotImplementedError):
        stream.wait_beat()
    assert stream.port_name is None
