"""AXI4-Lite register/CSR adapter (``AX-FR-080``).

A thin AXI4-Lite slave FSM maps the AXI channel handshake onto the
bus-agnostic :class:`~myhdl_addons.bus_common.RegisterEngine` request
interface (``req``/``we``/``addr``/``wdata``/``rdata``/``ack``).
"""

from __future__ import annotations

from typing import Any

from myhdl import Signal, SignalType, always, always_comb, block, intbv

from ..bus_common import RegisterEngine, RegisterSpec, bitfield, bitfield_set
from .status import RESP_OKAY

__all__ = ["AxiLiteCSR", "RegisterSpec", "bitfield", "bitfield_set"]


class AxiLiteCSR:
    """Declarative CSR front-end for an AXI4-Lite slave port."""

    def __init__(self, width: int = 32, gran: int = 8, name: str = "csr") -> None:
        self._engine = RegisterEngine(width=width, gran=gran, name=name)

    # -- declarative API (delegated) ---------------------------------------
    def add_write(
        self, offset: int, name: str, init: int = 0, w1c: bool = False
    ) -> RegisterSpec:
        return self._engine.add_write(offset, name, init, w1c)

    def add_read(self, offset: int, name: str, source: Any = None) -> RegisterSpec:
        return self._engine.add_read(offset, name, source)

    def add_ro(self, offset: int, name: str, init: int = 0) -> RegisterSpec:
        return self._engine.add_ro(offset, name, init)

    @property
    def signals(self) -> dict[str, SignalType]:
        return self._engine.signals

    @property
    def wr(self) -> dict[str, SignalType]:
        return self._engine.wr

    @property
    def rd(self) -> dict[str, SignalType]:
        return self._engine.rd

    # -- elaboration -------------------------------------------------------
    @block
    def build(self, port: Any):
        """Create the AXI4-Lite CSR peripheral and return its instances."""
        eng = self._engine
        width = eng.width
        strb_width = width // 8
        addr_width = len(port.awaddr)
        base = getattr(port, "base", 0) or 0

        req = Signal(bool(0))
        we = Signal(bool(0))
        addr = Signal(intbv(0)[addr_width:])
        wdata = Signal(intbv(0)[width:])
        wstrb = Signal(intbv(0)[strb_width:])
        rdata = Signal(intbv(0)[width:])
        ack = Signal(bool(0))

        bvalid = Signal(bool(0))
        rvalid = Signal(bool(0))
        bresp = Signal(intbv(0)[2:])
        rresp = Signal(intbv(0)[2:])
        rdata_r = Signal(intbv(0)[width:])

        engine = eng.build(
            port.aclk,
            port.aresetn,
            req,
            we,
            addr,
            wdata,
            rdata,
            ack,
            wstrb=wstrb,
            reset_active=0,
        )

        @always_comb
        def req_logic():
            req.next = 0
            we.next = 0
            addr.next = 0
            wdata.next = 0
            wstrb.next = 0
            if port.awvalid and port.wvalid:
                req.next = 1
                we.next = 1
                if port.awaddr >= base:
                    addr.next = port.awaddr - base
                wdata.next = port.wdata
                wstrb.next = port.wstrb
            elif port.arvalid:
                req.next = 1
                if port.araddr >= base:
                    addr.next = port.araddr - base

        @always(port.aclk.posedge)
        def resp():
            if not port.aresetn:
                bvalid.next = 0
                rvalid.next = 0
                bresp.next = RESP_OKAY
                rresp.next = RESP_OKAY
                rdata_r.next = 0
            else:
                # use the engine's acknowledged request (ack, we) rather than
                # re-decoding the AXI valids, so the produced ack is consumed.
                if ack and we and not bvalid:
                    bvalid.next = 1
                    bresp.next = RESP_OKAY
                elif bvalid and port.bready:
                    bvalid.next = 0
                if ack and (not we) and not rvalid:
                    rvalid.next = 1
                    rresp.next = RESP_OKAY
                    rdata_r.next = rdata
                elif rvalid and port.rready:
                    rvalid.next = 0

        @always_comb
        def outputs():
            port.awready.next = not bvalid
            port.wready.next = not bvalid
            port.arready.next = not rvalid
            port.bvalid.next = bvalid
            port.rvalid.next = rvalid
            port.bresp.next = bresp
            port.rresp.next = rresp
            port.rdata.next = rdata_r

        return engine, req_logic, resp, outputs
