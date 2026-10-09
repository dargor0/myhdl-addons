"""Q31-to-Wishbone bus master with two arbitrated clients (``RC-FR-100/101/104/106``).

:class:`BusMaster` adapts the core's uniform router protocol (Q31 /
``RC-FR-104``) onto a Wishbone B4 classic master port (``RC-FR-100/101``).  It
gives the memory router **one external bus backend**: two Q31 clients — the
instruction (``c0``) and data (``c1``) ports — share a single master and are
**arbitrated** so a bus reachable by both never deadlocks (``RC-FR-106``); the
unselected client simply waits for its response.

Each accepted client request becomes one classic Wishbone read or write.  A
store's bytes are placed and its ``SEL`` strobes raised from ``size``/``addr``;
reads return ``dat_i`` and errors surface through ``err_i``.  ``req_valid`` is
held by the client until its ``resp_valid`` pulse, so the bus tolerates wait
states (``RC-FR-104``) and keeps one outstanding access per client.

The Wishbone master itself is the reusable
:func:`~myhdl_addons.wishbone.wishbone_master`; the adapter adds the arbiter
and the Q31 handshake.  The flat ``wb_*`` ports are the master-side Wishbone
signals.

The ``transport`` parameter selects the backend (``RC-FR-101``): ``"wishbone"``
is available now; ``"axi"`` (AXI4-Lite) is rejected here and added at the
multiple-external-bus milestone (M5 / ``WP-34``), so a configured transport is
never silently served by the wrong master.
"""

from myhdl import Signal, always, always_comb, block, intbv

from ..common.config import ComponentBase, check_positive
from ..common.errors import HdlConfigError
from ..common.reset import make_reset
from ..common.views import SignalView
from ..wishbone import Wishbone, wishbone_master
from .config import AVAIL_BUS_TYPES

__all__ = ["AVAIL_TRANSPORTS", "BusMaster"]

#: Bus transports implemented by :class:`BusMaster`.  The config and
#: ``RC-FR-101`` also allow ``"axi"`` (AXI4-Lite); that backend is scheduled for
#: the multiple-external-bus milestone (M5 / ``WP-34``) and is rejected here so a
#: selection is never silently honoured by the wrong transport.
AVAIL_TRANSPORTS = ("wishbone",)


def _check_transport(transport) -> str:
    """Validate the bus transport (``RC-FR-101``); reject ones not yet built."""
    if transport not in AVAIL_BUS_TYPES:
        raise HdlConfigError(
            f"transport must be one of {AVAIL_BUS_TYPES}, got {transport!r}"
        )
    if transport not in AVAIL_TRANSPORTS:
        raise HdlConfigError(
            f"{transport!r} transport is scheduled for the multiple-external-bus "
            f"milestone (M5 / WP-34); available now: {AVAIL_TRANSPORTS}"
        )
    return transport


@block
def bus_store(wdata, wstrb, we, sel, dat_w, all_sel):
    """Drive ``DAT_W``/``SEL`` from the already-placed store bytes."""

    @always_comb
    def p():
        if we:
            dat_w.next = wdata
            sel.next = wstrb
        else:
            dat_w.next = 0
            sel.next = all_sel

    return p


class BusMaster(ComponentBase):
    """Two Q31 clients arbitrated onto one Wishbone master.

    Args:
        width: client address/data width (32 for RV32).
        transport: bus transport (``RC-FR-101``); ``"wishbone"`` now, ``"axi"``
            is rejected until M5 / ``WP-34``.
        data_width, adr_width: Wishbone bus geometry.
        reset_signal: reuse a specific ``ResetSignal``, or ``None``.

    Ports: ``clk``/``reset``/``wb_rst`` plus the flat Wishbone master side
    (``wb_cyc``/``wb_stb``/``wb_we``/``wb_adr``/``wb_dat_w``/``wb_sel`` out,
    ``wb_ack``/``wb_dat_r``/``wb_err`` in) and the two Q31 clients ``c0``
    (fetch, read-only: ``req_valid``/``req_addr``) and ``c1`` (data:
    ``req_valid``/``req_addr``/``req_we``/``req_wdata``/``req_wstrb``), each
    with ``resp_valid``/``resp_rdata``/``resp_error`` out.
    """

    def __init__(
        self,
        width: int = 32,
        transport: str = "wishbone",
        data_width: int = 32,
        adr_width: int = 16,
        reset_signal=None,
    ) -> None:
        self._params = {
            "width": check_positive(width, "width"),
            "transport": _check_transport(transport),
            "data_width": check_positive(data_width, "data_width"),
            "adr_width": check_positive(adr_width, "adr_width"),
            "reset_signal": make_reset(reset_signal),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        data_width = self._params["data_width"]
        adr_width = self._params["adr_width"]
        clk = Signal(bool(0))
        wb_rst = Signal(bool(0))
        bus = Wishbone(
            clk, wb_rst, data_width=data_width, adr_width=adr_width, err=True
        )
        self._master = bus.add_master("core")
        master = self._master
        sig = {
            "clk": clk,
            "reset": self._params["reset_signal"],
            "wb_rst": wb_rst,
            "wb_cyc": master.cyc_o,
            "wb_stb": master.stb_o,
            "wb_we": master.we_o,
            "wb_adr": master.adr_o,
            "wb_dat_w": master.dat_o,
            "wb_sel": master.sel_o,
            "wb_ack": master.ack_i,
            "wb_dat_r": master.dat_i,
            "wb_err": master.err_i,
        }
        for client in ("c0", "c1"):
            sig[f"{client}_req_valid"] = Signal(bool(0))
            sig[f"{client}_req_addr"] = Signal(intbv(0)[width:])
            sig[f"{client}_resp_valid"] = Signal(bool(0))
            sig[f"{client}_resp_rdata"] = Signal(intbv(0)[width:])
            sig[f"{client}_resp_error"] = Signal(bool(0))
        # c0 is the read-only fetch client; c1 carries the store fields.
        sig["c1_req_we"] = Signal(bool(0))
        sig["c1_req_wdata"] = Signal(intbv(0)[width:])
        sig["c1_req_wstrb"] = Signal(intbv(0)[width // 8 :])
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the adapter onto *ports* and return its instances."""
        width = self._params["width"]
        adr_width = self._params["adr_width"]
        data_width = self._params["data_width"]
        active = int(self._params["reset_signal"].active)
        all_sel = (1 << (data_width // 8)) - 1

        req = Signal(bool(0))
        adr = Signal(intbv(0)[adr_width:])
        we = Signal(bool(0))
        dat_w = Signal(intbv(0)[data_width:])
        sel = Signal(intbv(0)[data_width // 8 :])
        busy = Signal(bool(0))
        done = Signal(bool(0))
        dat_r = Signal(intbv(0)[data_width:])
        err = Signal(bool(0))

        state = Signal(intbv(0)[2:])
        owner = Signal(bool(0))
        adr_l = Signal(intbv(0)[width:])
        we_l = Signal(bool(0))
        wdata_l = Signal(intbv(0)[width:])
        wstrb_l = Signal(intbv(0)[width // 8 :])

        @always_comb
        def drive_wb_reset():
            ports.wb_rst.next = ports.reset == active

        @always_comb
        def drive_command():
            # one request pulse while in the START state; the latched address,
            # write data and strobes are already valid then
            req.next = state == 1
            we.next = we_l
            adr.next = adr_l

        @always(ports.clk.posedge)
        def fsm():
            if ports.reset == active:
                state.next = 0
                owner.next = 0
                ports.c0_resp_valid.next = 0
                ports.c1_resp_valid.next = 0
            else:
                ports.c0_resp_valid.next = 0
                ports.c1_resp_valid.next = 0
                if state == 0:
                    if not busy:
                        if ports.c0_req_valid:
                            owner.next = 0
                            adr_l.next = ports.c0_req_addr
                            we_l.next = 0
                            wdata_l.next = 0
                            wstrb_l.next = all_sel
                            state.next = 1
                        elif ports.c1_req_valid:
                            owner.next = 1
                            adr_l.next = ports.c1_req_addr
                            we_l.next = ports.c1_req_we
                            wdata_l.next = ports.c1_req_wdata
                            wstrb_l.next = ports.c1_req_wstrb
                            state.next = 1
                elif state == 1:
                    state.next = 2
                else:
                    if done:
                        if owner == 0:
                            ports.c0_resp_valid.next = 1
                            ports.c0_resp_rdata.next = dat_r
                            ports.c0_resp_error.next = err
                        else:
                            ports.c1_resp_valid.next = 1
                            ports.c1_resp_rdata.next = dat_r
                            ports.c1_resp_error.next = err
                        state.next = 0

        return [
            wishbone_master(
                self._master, req, adr, we, dat_w, sel, busy, done, dat_r, err
            ),
            bus_store(wdata_l, wstrb_l, we_l, sel, dat_w, all_sel),
            drive_wb_reset,
            drive_command,
            fsm,
        ]
