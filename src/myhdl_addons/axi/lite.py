"""AXI4-Lite master core (``AX-FR-040``).

A small single-beat master with a convertible command interface:
``start``/``write``/``addr``/``wdata``/``wstrb`` in, ``busy``/``done``/
``rdata``/``resp`` out.  One transaction at a time.
"""

from __future__ import annotations

from typing import Any

from myhdl import Signal, always, always_comb, block, intbv

__all__ = ["axi_lite_master"]

_IDLE, _W_ADDR, _W_RESP, _R_ADDR, _R_RESP = 0, 1, 2, 3, 4
_NSTATES = 5


@block
def axi_lite_master(
    port: Any,
    start: Any,
    write: Any,
    addr: Any,
    wdata: Any,
    wstrb: Any,
    busy: Any,
    done: Any,
    rdata: Any,
    resp: Any,
):
    """A single-beat AXI4-Lite master.

    Args:
        port: an :class:`AxiMasterView` for the ``lite`` variant.
        start, write, addr, wdata, wstrb: command inputs (pulse ``start``).
        busy, done, rdata, resp: status/response outputs.
    """
    addr_width = len(port.awaddr)
    dw = len(port.wdata)
    sw = len(port.wstrb)

    state = Signal(intbv(_IDLE, min=0, max=_NSTATES))
    addr_r = Signal(intbv(0)[addr_width:])
    data_r = Signal(intbv(0)[dw:])
    strb_r = Signal(intbv(0)[sw:])
    rdata_r = Signal(intbv(0)[dw:])
    resp_r = Signal(intbv(0)[2:])

    @always_comb
    def outputs():
        port.awaddr.next = addr_r
        port.awprot.next = 0
        port.awvalid.next = 0
        port.wdata.next = data_r
        port.wstrb.next = strb_r
        port.wvalid.next = 0
        port.bready.next = 0
        port.araddr.next = addr_r
        port.arprot.next = 0
        port.arvalid.next = 0
        port.rready.next = 0
        if state == _W_ADDR:
            port.awvalid.next = 1
            port.wvalid.next = 1
        elif state == _W_RESP:
            port.bready.next = 1
        elif state == _R_ADDR:
            port.arvalid.next = 1
        elif state == _R_RESP:
            port.rready.next = 1
        busy.next = state != _IDLE
        done.next = (state == _W_RESP and port.bvalid) or (
            state == _R_RESP and port.rvalid
        )
        if state == _W_RESP:
            rdata.next = rdata_r
            resp.next = port.bresp
        elif state == _R_RESP:
            rdata.next = port.rdata
            resp.next = port.rresp
        else:
            rdata.next = rdata_r
            resp.next = resp_r

    @always(port.aclk.posedge)
    def fsm():
        if not port.aresetn:
            state.next = _IDLE
        elif state == _IDLE:
            if start:
                addr_r.next = addr
                data_r.next = wdata
                strb_r.next = wstrb
                if write:
                    state.next = _W_ADDR
                else:
                    state.next = _R_ADDR
        elif state == _W_ADDR:
            if port.awready and port.wready:
                state.next = _W_RESP
        elif state == _W_RESP:
            if port.bvalid:
                resp_r.next = port.bresp
                state.next = _IDLE
        elif state == _R_ADDR:
            if port.arready:
                state.next = _R_RESP
        elif state == _R_RESP and port.rvalid:
            rdata_r.next = port.rdata
            resp_r.next = port.rresp
            state.next = _IDLE

    return fsm, outputs
