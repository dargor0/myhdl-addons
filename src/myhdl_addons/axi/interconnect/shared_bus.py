"""Basic multi-master AXI fabric (shared bus).

Implements a single-outstanding, arbitrated shared bus for the ``lite`` and
``full`` variants: every master is arbitrated onto one slave-facing channel set,
the address is decoded to one slave, and responses are routed back to the
granted master (``AX-FR-061``).  This is the simpler alternative to the
full-mesh crossbar.

For the ``full`` variant the granted master's ``AWID``/``ARID`` presented to the
slave is replaced by a per-slave unique value (the originating master index),
and the master's original ID is restored on the ``B``/``R`` responses; the read
grant is held until ``RLAST``.

Convertibility notes
--------------------

A single list cannot hold the port signals because their types/widths differ
(``bool`` plus several ``intbv`` widths), and MyHDL rejects such mixed lists.
Instead every signal gets its own homogeneous per-master / per-slave list, and
each shared-bus signal is driven by exactly one small process.  The mux/fanout
processes use ``@always_comb``: it runs at time 0 and extends every element of
a referenced signal list into its sensitivity, so both the initial default
levels and later list-element changes are tracked.
"""

from __future__ import annotations

from myhdl import Signal, always, always_comb, block, intbv

from ...bus_common import address_decoder
from ..checks import AxiConfigError
from ..interface import MASTER_OUT, SLAVE_OUT
from ..protocol import check_no_contention
from ..status import RESP_DECERR
from .base import AxiContext, AxiInterconnectBase

__all__ = ["AxiSharedBus"]

_GATED_OUT = ("awvalid", "wvalid", "arvalid")
_GATED_IN = ("awready", "wready", "arready", "bvalid", "rvalid")


def _clone(sig):
    if isinstance(sig.val, bool):
        return Signal(bool(0))
    return Signal(intbv(0)[len(sig.val) :])


# -- reusable convertible helpers -----------------------------------------
# ``_GATED_OUT`` signals are qualified by the per-slave select; all others are
# broadcast.  Each helper drives exactly one destination list/scalar.


@block
def bus_mux(grants, srcs, dst, n):
    """Drive ``dst`` with the granted master's signal (0 if none granted)."""

    @always_comb
    def p():
        dst.next = 0
        for i in range(n):
            if grants[i]:
                dst.next = srcs[i]

    return p


@block
def bus_mux_index(grants, dst, n):
    """Drive ``dst`` with the index of the granted master (ID remap)."""

    @always_comb
    def p():
        dst.next = 0
        for i in range(n):
            if grants[i]:
                dst.next = i

    return p


@block
def bus_fanout_gated(src, dsts, sels, n):
    """Broadcast ``src`` to every slave, qualified by ``sels[j]``."""

    @always_comb
    def p():
        for j in range(n):
            dsts[j].next = src and sels[j]

    return p


@block
def bus_fanout_plain(src, dsts, n):
    """Broadcast ``src`` to every slave."""

    @always_comb
    def p():
        for j in range(n):
            dsts[j].next = src

    return p


@block
def bus_resp_mux(sels, srcs, dst, n):
    """Select the addressed slave's response signal."""

    @always_comb
    def p():
        dst.next = 0
        for j in range(n):
            if sels[j]:
                dst.next = srcs[j]

    return p


@block
def bus_resp_ready(sels, srcs, dst, sel_any, n):
    """Response mux with the default-slave ``ready`` level when unselected."""

    @always_comb
    def p():
        dst.next = 0
        for j in range(n):
            if sels[j]:
                dst.next = srcs[j]
        if not sel_any:
            dst.next = 1

    return p


@block
def bus_resp_write(sels, srcs, dst, sel_any, active, write_r, decerr, n):
    """Response mux for write-channel signals, defaulting to ``DECERR``.

    The default (unmapped) response is qualified by ``active`` so it appears
    only after the request has been granted -- asserting it combinationally
    would let the FSM observe an early response and release the bus before the
    master sampled it.
    """

    @always_comb
    def p():
        dst.next = 0
        for j in range(n):
            if sels[j]:
                dst.next = srcs[j]
        if active and not sel_any and write_r:
            dst.next = decerr

    return p


@block
def bus_resp_read(sels, srcs, dst, sel_any, active, write_r, decerr, n):
    """Response mux for read-channel signals, defaulting to ``DECERR``."""

    @always_comb
    def p():
        dst.next = 0
        for j in range(n):
            if sels[j]:
                dst.next = srcs[j]
        if active and not sel_any and not write_r:
            dst.next = decerr

    return p


@block
def bus_mresp_gated(src, dsts, grants, n):
    """Route the shared response to the granted master, gated by its grant."""

    @always_comb
    def p():
        for i in range(n):
            dsts[i].next = src and grants[i]

    return p


@block
def bus_mresp_plain(src, dsts, n):
    """Broadcast the shared response to every master."""

    @always_comb
    def p():
        for i in range(n):
            dsts[i].next = src

    return p


@block
def bus_mresp_id(src, dsts, grants, orig_id, write_r, when_write, n):
    """Route a response ID, restoring the master's original ID when granted."""

    @always_comb
    def p():
        for i in range(n):
            dsts[i].next = src
        for i in range(n):
            if grants[i] and (write_r == when_write):
                dsts[i].next = orig_id

    return p


class AxiSharedBus(AxiInterconnectBase):
    """A single-outstanding, arbitrated AXI4-Lite / AXI4 shared bus."""

    name = "shared_bus"

    @block
    def build(self, ctx: AxiContext):
        variant = ctx.variant
        if variant not in ("lite", "full"):
            raise AxiConfigError("AxiSharedBus supports the 'lite' and 'full' variants")
        masters = ctx.masters
        slaves = ctx.slaves
        nm = len(masters)
        ns = len(slaves)
        if nm < 1 or ns < 1:
            raise AxiConfigError("AxiSharedBus needs at least one master and one slave")
        out_names = list(MASTER_OUT[variant])
        in_names = list(SLAVE_OUT[variant])
        is_full = variant == "full"
        id_width = ctx.id_width
        if is_full and (1 << id_width) < nm:
            raise AxiConfigError(
                f"id_width={id_width} cannot host {nm} unique remapped IDs"
            )

        # per-name shared-bus signals and per-endpoint homogeneous signal lists
        s_out = {name: _clone(getattr(masters[0], name)) for name in out_names}
        s_in = {name: _clone(getattr(masters[0], name)) for name in in_names}
        m_out = {name: [getattr(m, name) for m in masters] for name in out_names}
        m_in = {name: [getattr(m, name) for m in masters] for name in in_names}
        sl_in = {name: [getattr(s, name) for s in slaves] for name in out_names}
        sl_out = {name: [getattr(s, name) for s in slaves] for name in in_names}

        s_adr = _clone(masters[0].awaddr)
        m_awvalid = m_out["awvalid"]
        m_arvalid = m_out["arvalid"]
        s_awvalid = s_out["awvalid"]
        s_bready = s_out["bready"]
        s_rready = s_out["rready"]
        s_bvalid = s_in["bvalid"]
        s_rvalid = s_in["rvalid"]
        s_adr_aw = s_out["awaddr"]
        s_adr_ar = s_out["araddr"]
        m_awid = m_out["awid"] if is_full else None
        m_arid = m_out["arid"] if is_full else None
        s_rlast = s_in["rlast"] if is_full else None

        selects = [Signal(bool(0)) for _ in range(ns)]
        sel_latched = [Signal(bool(0)) for _ in range(ns)]
        reqs = [Signal(bool(0)) for _ in range(nm)]
        grants = [Signal(bool(0)) for _ in range(nm)]
        active = Signal(bool(0))
        owner = Signal(intbv(0, min=0, max=nm))
        write_r = Signal(bool(0))
        orig_id = Signal(intbv(0)[id_width:])
        sel_any = Signal(bool(0))

        dec = address_decoder(
            s_adr, selects, ctx.address_map.bases(), ctx.address_map.sizes()
        )

        @always_comb
        def req_logic():
            for i in range(nm):
                reqs[i].next = m_awvalid[i] or m_arvalid[i]

        @always_comb
        def grant_logic():
            for i in range(nm):
                grants[i].next = 0
            if active:
                for i in range(nm):
                    if owner == i:
                        grants[i].next = 1
            else:
                blocked = False
                for i in range(nm):
                    if reqs[i] and not blocked:
                        grants[i].next = 1
                        blocked = True

        if is_full:

            @always(ctx.aclk.posedge)
            def state():
                if not ctx.aresetn:
                    active.next = 0
                    owner.next = 0
                    write_r.next = 0
                    orig_id.next = 0
                    for j in range(ns):
                        sel_latched[j].next = 0
                elif not active:
                    grant_i = -1
                    for i in range(nm):
                        if reqs[i] and grant_i < 0:
                            grant_i = i
                    if grant_i >= 0:
                        owner.next = grant_i
                        active.next = 1
                        write_r.next = m_awvalid[grant_i]
                        if m_awvalid[grant_i]:
                            orig_id.next = m_awid[grant_i]
                        else:
                            orig_id.next = m_arid[grant_i]
                        for j in range(ns):
                            sel_latched[j].next = selects[j]
                else:
                    done = s_bvalid and s_bready
                    if not done:
                        done = s_rvalid and s_rready and s_rlast
                    if done:
                        active.next = 0

        else:

            @always(ctx.aclk.posedge)
            def state():
                if not ctx.aresetn:
                    active.next = 0
                    owner.next = 0
                    write_r.next = 0
                    for j in range(ns):
                        sel_latched[j].next = 0
                elif not active:
                    grant_i = -1
                    for i in range(nm):
                        if reqs[i] and grant_i < 0:
                            grant_i = i
                    if grant_i >= 0:
                        owner.next = grant_i
                        active.next = 1
                        write_r.next = m_awvalid[grant_i]
                        for j in range(ns):
                            sel_latched[j].next = selects[j]
                else:
                    done = s_bvalid and s_bready
                    if not done:
                        done = s_rvalid and s_rready
                    if done:
                        active.next = 0

        @always_comb
        def address_mux():
            if s_awvalid:
                s_adr.next = s_adr_aw
            else:
                s_adr.next = s_adr_ar

        @always_comb
        def sel_any_logic():
            sel_any.next = 0
            for j in range(ns):
                if sel_latched[j]:
                    sel_any.next = 1

        proclist = [dec, req_logic, grant_logic, state, address_mux, sel_any_logic]

        # master mux onto the shared bus
        for name in out_names:
            if is_full and name in ("awid", "arid"):
                proclist.append(bus_mux_index(grants, s_out[name], nm))
            else:
                proclist.append(bus_mux(grants, m_out[name], s_out[name], nm))

        # broadcast to the slaves (valids gated by the address decode)
        for name in out_names:
            if name in _GATED_OUT:
                proclist.append(
                    bus_fanout_gated(s_out[name], sl_in[name], sel_latched, ns)
                )
            else:
                proclist.append(bus_fanout_plain(s_out[name], sl_in[name], ns))

        # slave response mux back onto the shared bus
        for name in in_names:
            if name in ("awready", "wready", "arready"):
                proclist.append(
                    bus_resp_ready(sel_latched, sl_out[name], s_in[name], sel_any, ns)
                )
            elif name == "bvalid":
                proclist.append(
                    bus_resp_write(
                        sel_latched,
                        sl_out[name],
                        s_in[name],
                        sel_any,
                        active,
                        write_r,
                        1,
                        ns,
                    )
                )
            elif name == "bresp":
                proclist.append(
                    bus_resp_write(
                        sel_latched,
                        sl_out[name],
                        s_in[name],
                        sel_any,
                        active,
                        write_r,
                        RESP_DECERR,
                        ns,
                    )
                )
            elif name == "rvalid":
                proclist.append(
                    bus_resp_read(
                        sel_latched,
                        sl_out[name],
                        s_in[name],
                        sel_any,
                        active,
                        write_r,
                        1,
                        ns,
                    )
                )
            elif name == "rresp":
                proclist.append(
                    bus_resp_read(
                        sel_latched,
                        sl_out[name],
                        s_in[name],
                        sel_any,
                        active,
                        write_r,
                        RESP_DECERR,
                        ns,
                    )
                )
            elif name == "rlast":
                proclist.append(
                    bus_resp_read(
                        sel_latched,
                        sl_out[name],
                        s_in[name],
                        sel_any,
                        active,
                        write_r,
                        1,
                        ns,
                    )
                )
            else:
                proclist.append(bus_resp_mux(sel_latched, sl_out[name], s_in[name], ns))

        # route the shared response back to the masters
        for name in in_names:
            if name == "bid":
                proclist.append(
                    bus_mresp_id(
                        s_in[name], m_in[name], grants, orig_id, write_r, True, nm
                    )
                )
            elif name == "rid":
                proclist.append(
                    bus_mresp_id(
                        s_in[name], m_in[name], grants, orig_id, write_r, False, nm
                    )
                )
            elif name in _GATED_IN:
                proclist.append(bus_mresp_gated(s_in[name], m_in[name], grants, nm))
            else:
                proclist.append(bus_mresp_plain(s_in[name], m_in[name], nm))

        if ctx.trace.enabled:
            proclist.append(
                check_no_contention(
                    ctx.aclk, ctx.aresetn, grants, label="shared_bus", trace=ctx.trace
                )
            )

        return proclist
