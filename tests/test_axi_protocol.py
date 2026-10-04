"""AXI protocol assertions (AX-FR-100)."""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import AxiProtocolError, check_valid_stable


@block
def _tb(stim_kind):
    clk = Signal(bool(0))
    rst = Signal(bool(1))
    valid = Signal(bool(0))
    ready = Signal(bool(0))
    data = Signal(intbv(0)[8:])

    mon = check_valid_stable(clk, rst, valid, ready, [data], label="aw")

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
        if stim_kind == "payload":
            data.next = 2  # changed while waiting for READY
        elif stim_kind == "withdraw":
            valid.next = 0  # withdrawn before READY
        else:
            yield clk.posedge
            ready.next = 1

    @instance
    def stopper():
        yield delay(1000)
        raise StopSimulation

    return clkgen, mon, stim, stopper


def test_payload_change_raises():
    with pytest.raises(AxiProtocolError):
        _tb("payload").run_sim()


def test_valid_withdraw_raises():
    with pytest.raises(AxiProtocolError):
        _tb("withdraw").run_sim()


def test_stable_handshake_ok():
    _tb("ok").run_sim()
