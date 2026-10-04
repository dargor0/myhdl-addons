"""Basic full-mesh AXI crossbar (``AX-FR-060``, ``AX-FR-062``).

Every master is decoded to its target slave; each slave arbitrates the masters
that target it, so *different* slaves can serve *different* masters
concurrently (a full mesh).  Both the AXI4-Lite (``lite``) and AXI4 (``full``)
variants are supported.

For the ``full`` variant the crossbar **remaps IDs**: the granted master's
``AWID``/``ARID`` presented to the slave is replaced by a per-slave unique value
(the originating master index), and the master's original ID is restored on the
``B``/``R`` responses.  This keeps IDs unique per slave when several masters
share it.  The implementation is single-outstanding per master and per slave,
matching the shipped master/slave blocks.

Convertibility notes
--------------------

Port signals mix ``bool`` with several ``intbv`` widths, so they cannot share a
signal list (MyHDL rejects mixed lists).  Every signal therefore gets its own
homogeneous per-master / per-slave list, each shared verdict is driven by one
small process, and the request/grant matrices are flat homogeneous lists.  The
combinational processes use ``@always_comb`` so they settle at time 0 and track
every element of the signal lists they reference.
"""

from __future__ import annotations

from myhdl import Signal, always, always_comb, block, intbv

from ...bus_common import address_decoder
from ..checks import AxiConfigError
from ..interface import MASTER_OUT, SLAVE_OUT
from ..protocol import check_no_contention
from ..status import RESP_DECERR
from .base import AxiContext, AxiInterconnectBase

__all__ = ["AxiCrossbar"]


def _clone(sig):
    if isinstance(sig.val, bool):
        return Signal(bool(0))
    return Signal(intbv(0)[len(sig.val) :])


@block
def xbar_addr_mux(awvalid, awaddr, araddr, dst, n):
    """Per-master address mux: prefer the write address when writing."""

    @always_comb
    def p():
        for i in range(n):
            if awvalid[i]:
                dst[i].next = awaddr[i]
            else:
                dst[i].next = araddr[i]

    return p


@block
def xbar_req_row(req_i, sel_row, req_ij, base, ns):
    """Per-master request row: ``req_ij[base+j] = sel_row[j] and req_i``."""

    @always_comb
    def p():
        for j in range(ns):
            req_ij[base + j].next = sel_row[j] and req_i

    return p


@block
def xbar_any_row(sel_row, any_sig, ns):
    """Set ``any_sig`` when any slave is selected for one master."""

    @always_comb
    def p():
        any_sig.next = 0
        for j in range(ns):
            if sel_row[j]:
                any_sig.next = 1

    return p


@block
def xbar_fanout(g_ij, srcs, dsts, nm, ns):
    """Mux the granted master's signal onto each slave input."""

    @always_comb
    def p():
        for j in range(ns):
            dsts[j].next = 0
        for j in range(ns):
            for i in range(nm):
                if g_ij[i * ns + j]:
                    dsts[j].next = srcs[i]

    return p


@block
def xbar_fanout_index(g_ij, dsts, nm, ns):
    """Drive each slave input with the granted master index (ID remap)."""

    @always_comb
    def p():
        for j in range(ns):
            dsts[j].next = 0
        for j in range(ns):
            for i in range(nm):
                if g_ij[i * ns + j]:
                    dsts[j].next = i

    return p


@block
def xbar_mresp_ready(g_ij, srcs, dsts, d_active, nm, ns):
    """Route a slave ``ready`` response, defaulting high for the default slave."""

    @always_comb
    def p():
        for i in range(nm):
            dsts[i].next = 0
        for j in range(ns):
            for i in range(nm):
                if g_ij[i * ns + j]:
                    dsts[i].next = srcs[j]
        for i in range(nm):
            if d_active[i]:
                dsts[i].next = 1

    return p


@block
def xbar_mresp_wr(g_ij, srcs, dsts, d_active, d_write, decerr, is_write, nm, ns):
    """Route a write/read response, defaulting to ``decerr`` for the default slave."""

    @always_comb
    def p():
        for i in range(nm):
            dsts[i].next = 0
        for j in range(ns):
            for i in range(nm):
                if g_ij[i * ns + j]:
                    dsts[i].next = srcs[j]
        for i in range(nm):
            if d_active[i] and (d_write[i] == is_write):
                dsts[i].next = decerr

    return p


@block
def xbar_mresp_plain(g_ij, srcs, dsts, nm, ns):
    """Route a plain slave response (e.g. ``RDATA``) to the granted master."""

    @always_comb
    def p():
        for i in range(nm):
            dsts[i].next = 0
        for j in range(ns):
            for i in range(nm):
                if g_ij[i * ns + j]:
                    dsts[i].next = srcs[j]

    return p


@block
def xbar_mresp_id(g_ij, srcs, dsts, write_r, orig_id, when_write, nm, ns):
    """Route a response ID, restoring the master's original ID when granted."""

    @always_comb
    def p():
        for i in range(nm):
            dsts[i].next = 0
        for j in range(ns):
            for i in range(nm):
                if g_ij[i * ns + j]:
                    dsts[i].next = srcs[j]
                    if write_r[j] == when_write:
                        dsts[i].next = orig_id[j]

    return p


class AxiCrossbar(AxiInterconnectBase):
    """A basic full-mesh AXI4-Lite / AXI4 crossbar."""

    name = "crossbar"

    @block
    def build(self, ctx: AxiContext):
        variant = ctx.variant
        if variant not in ("lite", "full"):
            raise AxiConfigError("AxiCrossbar supports the 'lite' and 'full' variants")
        masters = ctx.masters
        slaves = ctx.slaves
        nm = len(masters)
        ns = len(slaves)
        if nm < 1 or ns < 1:
            raise AxiConfigError("AxiCrossbar needs at least one master and one slave")
        out_names = list(MASTER_OUT[variant])
        in_names = list(SLAVE_OUT[variant])
        is_full = variant == "full"
        id_width = ctx.id_width
        if is_full and (1 << id_width) < nm:
            raise AxiConfigError(
                f"id_width={id_width} cannot host {nm} unique remapped IDs"
            )

        bases = ctx.address_map.bases()
        sizes = ctx.address_map.sizes()

        m_out = {name: [getattr(m, name) for m in masters] for name in out_names}
        m_in = {name: [getattr(m, name) for m in masters] for name in in_names}
        sl_in = {name: [getattr(s, name) for s in slaves] for name in out_names}
        sl_out = {name: [getattr(s, name) for s in slaves] for name in in_names}

        m_awvalid = m_out["awvalid"]
        m_arvalid = m_out["arvalid"]
        m_bready = m_out["bready"]
        m_rready = m_out["rready"]
        m_awid = m_out["awid"] if is_full else None
        m_arid = m_out["arid"] if is_full else None
        s_bvalid = sl_out["bvalid"]
        s_rvalid = sl_out["rvalid"]
        s_rlast = sl_out["rlast"] if is_full else None

        m_adr = [_clone(masters[0].awaddr) for _ in range(nm)]
        m_sel_lists = [[Signal(bool(0)) for _ in range(ns)] for _ in range(nm)]
        m_req = [Signal(bool(0)) for _ in range(nm)]
        m_sel_any = [Signal(bool(0)) for _ in range(nm)]
        req_ij = [Signal(bool(0)) for _ in range(nm * ns)]
        g_ij = [Signal(bool(0)) for _ in range(nm * ns)]
        active = [Signal(bool(0)) for _ in range(ns)]
        owner = [Signal(intbv(0, min=0, max=nm)) for _ in range(ns)]
        d_active = [Signal(bool(0)) for _ in range(nm)]
        d_write = [Signal(bool(0)) for _ in range(nm)]
        write_r = [Signal(bool(0)) for _ in range(ns)]
        orig_id = [Signal(intbv(0)[id_width:]) for _ in range(ns)]

        proclist = []
        for i in range(nm):
            proclist.append(address_decoder(m_adr[i], m_sel_lists[i], bases, sizes))

        proclist.append(
            xbar_addr_mux(m_awvalid, m_out["awaddr"], m_out["araddr"], m_adr, nm)
        )

        for i in range(nm):
            proclist.append(xbar_req_row(m_req[i], m_sel_lists[i], req_ij, i * ns, ns))
            proclist.append(xbar_any_row(m_sel_lists[i], m_sel_any[i], ns))

        @always_comb
        def req_logic():
            for i in range(nm):
                m_req[i].next = m_awvalid[i] or m_arvalid[i]

        proclist.append(req_logic)

        @always_comb
        def grant_logic():
            for k in range(nm * ns):
                g_ij[k].next = 0
            for j in range(ns):
                if active[j]:
                    for i in range(nm):
                        if owner[j] == i:
                            g_ij[i * ns + j].next = 1
                else:
                    blocked = False
                    for i in range(nm):
                        if req_ij[i * ns + j] and not blocked:
                            g_ij[i * ns + j].next = 1
                            blocked = True

        proclist.append(grant_logic)

        if is_full:

            @always(ctx.aclk.posedge)
            def state():
                if not ctx.aresetn:
                    for j in range(ns):
                        active[j].next = 0
                        owner[j].next = 0
                        write_r[j].next = 0
                        orig_id[j].next = 0
                else:
                    for j in range(ns):
                        if not active[j]:
                            found = False
                            for i in range(nm):
                                if req_ij[i * ns + j] and not found:
                                    owner[j].next = i
                                    active[j].next = 1
                                    found = True
                                    write_r[j].next = m_awvalid[i]
                                    if m_awvalid[i]:
                                        orig_id[j].next = m_awid[i]
                                    else:
                                        orig_id[j].next = m_arid[i]
                        else:
                            done = s_bvalid[j] and m_bready[owner[j]]
                            if not done:
                                done = s_rvalid[j] and m_rready[owner[j]] and s_rlast[j]
                            if done:
                                active[j].next = 0

        else:

            @always(ctx.aclk.posedge)
            def state():
                if not ctx.aresetn:
                    for j in range(ns):
                        active[j].next = 0
                        owner[j].next = 0
                        write_r[j].next = 0
                else:
                    for j in range(ns):
                        if not active[j]:
                            found = False
                            for i in range(nm):
                                if req_ij[i * ns + j] and not found:
                                    owner[j].next = i
                                    active[j].next = 1
                                    found = True
                                    write_r[j].next = m_awvalid[i]
                        else:
                            done = s_bvalid[j] and m_bready[owner[j]]
                            if not done:
                                done = s_rvalid[j] and m_rready[owner[j]]
                            if done:
                                active[j].next = 0

        proclist.append(state)

        @always(ctx.aclk.posedge)
        def default_state():
            if not ctx.aresetn:
                for i in range(nm):
                    d_active[i].next = 0
                    d_write[i].next = 0
            else:
                for i in range(nm):
                    if not d_active[i]:
                        if m_req[i] and (not m_sel_any[i]):
                            d_active[i].next = 1
                            d_write[i].next = m_awvalid[i]
                    else:
                        done = (d_write[i] and m_bready[i]) or (
                            (not d_write[i]) and m_rready[i]
                        )
                        if done:
                            d_active[i].next = 0

        proclist.append(default_state)

        for name in out_names:
            if is_full and name in ("awid", "arid"):
                proclist.append(xbar_fanout_index(g_ij, sl_in[name], nm, ns))
            else:
                proclist.append(xbar_fanout(g_ij, m_out[name], sl_in[name], nm, ns))

        for name in in_names:
            if name in ("awready", "wready", "arready"):
                proclist.append(
                    xbar_mresp_ready(g_ij, sl_out[name], m_in[name], d_active, nm, ns)
                )
            elif name == "bvalid":
                proclist.append(
                    xbar_mresp_wr(
                        g_ij, sl_out[name], m_in[name], d_active, d_write, 1, 1, nm, ns
                    )
                )
            elif name == "bresp":
                proclist.append(
                    xbar_mresp_wr(
                        g_ij,
                        sl_out[name],
                        m_in[name],
                        d_active,
                        d_write,
                        RESP_DECERR,
                        1,
                        nm,
                        ns,
                    )
                )
            elif name == "rvalid":
                proclist.append(
                    xbar_mresp_wr(
                        g_ij, sl_out[name], m_in[name], d_active, d_write, 1, 0, nm, ns
                    )
                )
            elif name == "rresp":
                proclist.append(
                    xbar_mresp_wr(
                        g_ij,
                        sl_out[name],
                        m_in[name],
                        d_active,
                        d_write,
                        RESP_DECERR,
                        0,
                        nm,
                        ns,
                    )
                )
            elif name == "rlast":
                proclist.append(
                    xbar_mresp_wr(
                        g_ij, sl_out[name], m_in[name], d_active, d_write, 1, 0, nm, ns
                    )
                )
            elif name == "bid":
                proclist.append(
                    xbar_mresp_id(
                        g_ij, sl_out[name], m_in[name], write_r, orig_id, True, nm, ns
                    )
                )
            elif name == "rid":
                proclist.append(
                    xbar_mresp_id(
                        g_ij, sl_out[name], m_in[name], write_r, orig_id, False, nm, ns
                    )
                )
            else:
                proclist.append(
                    xbar_mresp_plain(g_ij, sl_out[name], m_in[name], nm, ns)
                )

        if ctx.trace.enabled:
            for j in range(ns):
                proclist.append(
                    check_no_contention(
                        ctx.aclk,
                        ctx.aresetn,
                        [g_ij[i * ns + j] for i in range(nm)],
                        label="crossbar",
                        trace=ctx.trace,
                    )
                )

        return proclist
