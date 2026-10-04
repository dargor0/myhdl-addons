"""Uniform reset convention (``IC-FR-005``).

Every clocked component exposes a ``reset`` port holding a
``myhdl.ResetSignal``; the active level comes from that object (default
active-low), the reset is always synchronous, and asynchronous or non-
``ResetSignal`` values are rejected at construction.
"""

import pytest
from myhdl import ResetSignal, Signal, StopSimulation, always, block, delay, instance

from myhdl_addons.common.errors import HdlTypeError
from myhdl_addons.common.reset import make_reset
from myhdl_addons.components import HdlConfigError, Register


def test_default_is_active_low_synchronous():
    reset = make_reset()
    assert reset.active is False
    assert not reset.isasync


def test_provided_reset_is_returned_unchanged():
    supplied = ResetSignal(0, active=1, isasync=False)
    assert make_reset(supplied) is supplied


def test_async_reset_rejected():
    with pytest.raises(HdlConfigError):
        make_reset(ResetSignal(0, active=0, isasync=True))
    with pytest.raises(HdlConfigError):
        Register(fields=[("q", 4)], reset_signal=ResetSignal(0, active=0, isasync=True))


def test_non_reset_signal_rejected():
    with pytest.raises(HdlTypeError):
        make_reset(Signal(bool(0)))


@block
def _active_high_tb(results):
    rst = ResetSignal(0, active=1, isasync=False)
    reg = Register(fields=[("q", 8)], en=True, reset_values={"q": 0}, reset_signal=rst)
    ports = reg.ports()
    dut = reg.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.en.next = 1
        ports.d_q.next = 0xAA
        ports.reset.next = 1  # active-high: asserted
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        ports.reset.next = 0  # release
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        raise StopSimulation

    return clkgen, dut, stim


def test_register_honours_active_high_reset():
    results = []
    _active_high_tb(results).run_sim()
    assert results == [0, 0xAA]
