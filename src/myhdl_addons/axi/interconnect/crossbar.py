"""Basic full-mesh AXI crossbar (``AX-FR-060``, ``AX-FR-062``).

Every master is decoded to its target slave; each slave arbitrates the masters
that target it, so *different* slaves can serve *different* masters
concurrently (a full mesh).  Both the AXI4-Lite (``lite``) and AXI4 (``full``)
variants are supported.

For the ``full`` variant the crossbar **remaps IDs**: the granted master's
``AWID``/``ARID`` presented to the slave is replaced by a per-slave unique value
(the originating master index), and the master's original ID is restored on the
``B``/``R`` responses.  The implementation is single-outstanding per master and
per slave.

Convertibility notes
--------------------

A list-of-signals indexed inside a process is converted by MyHDL into a Verilog
memory that is then continuously assigned (invalid RTL).  The per-master /
per-slave matrices are therefore just elaboration-time containers; every shared
verdict is driven by **elaboration-built chains of per-element stages** over
individual signals (see :mod:`myhdl_addons.bus_common.muxing`).
"""

from __future__ import annotations

from myhdl import Signal, always, always_comb, block, intbv

from ...bus_common import address_decoder
from ...bus_common.muxing import grant_chain, or_chain, select_chain
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


def _kind(sig):
    """Return ``(bool_out, width)`` for a signal."""
    if isinstance(sig.val, bool):
        return True, 0
    return False, len(sig.val)


@block
def addr_stage(awvalid, awaddr, araddr, dst):
    """Per-master address mux: prefer the write address when writing."""

    @always_comb
    def p():
        if awvalid:
            dst.next = awaddr
        else:
            dst.next = araddr

    return p


@block
def req_stage(m_awvalid, m_arvalid, req):
    """Per-master request: ``awvalid or arvalid``."""

    @always_comb
    def p():
        req.next = m_awvalid or m_arvalid

    return p


@block
def req_cell(sel, req, out):
    """One request-matrix cell: ``sel and req``."""

    @always_comb
    def p():
        out.next = sel and req

    return p


@block
def resp_ready(sel_out, out, d_active):
    """Master ready response: selected slave, else 1 for the default slave."""

    @always_comb
    def p():
        if d_active:
            out.next = 1
        else:
            out.next = sel_out

    return p


@block
def resp_wr(sel_out, out, d_active, d_write, is_write, default):
    """Master write/read response, defaulting to ``default`` for the default slave."""

    @always_comb
    def p():
        if d_active and (d_write == is_write):
            out.next = default
        else:
            out.next = sel_out

    return p


@block
def resp_id(sel_out, orig_sel, wr_sel, out, is_write):
    """Master response ID, restoring the originating slave's source ID."""

    @always_comb
    def p():
        if wr_sel == is_write:
            out.next = orig_sel
        else:
            out.next = sel_out

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
        m_req = [Signal(bool(0)) for _ in range(nm)]
        m_sel_any = [Signal(bool(0)) for _ in range(nm)]
        sel = [[Signal(bool(0)) for _ in range(ns)] for _ in range(nm)]
        req_ij = [[Signal(bool(0)) for _ in range(ns)] for _ in range(nm)]
        g_ij = [[Signal(bool(0)) for _ in range(ns)] for _ in range(nm)]
        active = [Signal(bool(0)) for _ in range(ns)]
        owner = [Signal(intbv(0, min=0, max=nm)) for _ in range(ns)]
        write_r = [Signal(bool(0)) for _ in range(ns)] if is_full else None
        orig_id = [Signal(intbv(0)[id_width:]) for _ in range(ns)] if is_full else None
        d_active = [Signal(bool(0)) for _ in range(nm)]
        d_write = [Signal(bool(0)) for _ in range(nm)]
        any_req = [Signal(bool(0)) for _ in range(ns)]
        owner_next = [Signal(intbv(0, min=0, max=nm)) for _ in range(ns)]
        awv_owner = [Signal(bool(0)) for _ in range(ns)] if is_full else None
        awid_owner = (
            [Signal(intbv(0)[id_width:]) for _ in range(ns)] if is_full else None
        )
        arid_owner = (
            [Signal(intbv(0)[id_width:]) for _ in range(ns)] if is_full else None
        )
        bready_owner = [Signal(bool(0)) for _ in range(ns)]
        rready_owner = [Signal(bool(0)) for _ in range(ns)]

        proclist = []
        for i in range(nm):
            proclist.append(address_decoder(m_adr[i], sel[i], bases, sizes))
            proclist.append(
                addr_stage(
                    m_awvalid[i], m_out["awaddr"][i], m_out["araddr"][i], m_adr[i]
                )
            )
            proclist.append(req_stage(m_awvalid[i], m_arvalid[i], m_req[i]))
            proclist.append(or_chain(sel[i], m_sel_any[i]))
            for j in range(ns):
                proclist.append(req_cell(sel[i][j], m_req[i], req_ij[i][j]))

        for j in range(ns):
            proclist.append(
                grant_chain(
                    active[j],
                    owner[j],
                    [req_ij[i][j] for i in range(nm)],
                    [g_ij[i][j] for i in range(nm)],
                )
            )
            proclist.append(or_chain([req_ij[i][j] for i in range(nm)], any_req[j]))
            proclist.append(
                select_chain(
                    [g_ij[i][j] for i in range(nm)],
                    list(range(nm)),
                    owner_next[j],
                    max(1, (nm - 1).bit_length()),
                    False,
                )
            )
            proclist.append(
                select_chain(
                    [g_ij[i][j] for i in range(nm)], m_bready, bready_owner[j], 0, True
                )
            )
            proclist.append(
                select_chain(
                    [g_ij[i][j] for i in range(nm)], m_rready, rready_owner[j], 0, True
                )
            )
            if is_full:
                proclist.append(
                    select_chain(
                        [g_ij[i][j] for i in range(nm)],
                        m_awvalid,
                        awv_owner[j],
                        0,
                        True,
                    )
                )
                proclist.append(
                    select_chain(
                        [g_ij[i][j] for i in range(nm)],
                        m_awid,
                        awid_owner[j],
                        id_width,
                        False,
                    )
                )
                proclist.append(
                    select_chain(
                        [g_ij[i][j] for i in range(nm)],
                        m_arid,
                        arid_owner[j],
                        id_width,
                        False,
                    )
                )

        # per-slave arbiter/served state
        for j in range(ns):
            proclist.append(
                state_stage(
                    ctx.aclk,
                    ctx.aresetn,
                    active[j],
                    owner[j],
                    write_r[j] if is_full else None,
                    orig_id[j] if is_full else None,
                    any_req[j],
                    owner_next[j],
                    awv_owner[j] if is_full else None,
                    awid_owner[j] if is_full else None,
                    arid_owner[j] if is_full else None,
                    s_bvalid[j],
                    bready_owner[j],
                    s_rvalid[j],
                    rready_owner[j],
                    s_rlast[j] if is_full else None,
                    is_full,
                )
            )

        for i in range(nm):
            proclist.append(
                default_stage(
                    ctx.aclk,
                    ctx.aresetn,
                    d_active[i],
                    d_write[i],
                    m_req[i],
                    m_sel_any[i],
                    m_awvalid[i],
                    m_bready[i],
                    m_rready[i],
                )
            )

        # fanout each master's signals to every slave (grant-selected)
        for name in out_names:
            bool_out, width = _kind(m_out[name][0])
            for j in range(ns):
                if is_full and name in ("awid", "arid"):
                    proclist.append(
                        select_chain(
                            [g_ij[i][j] for i in range(nm)],
                            list(range(nm)),
                            sl_in[name][j],
                            id_width,
                            False,
                        )
                    )
                else:
                    proclist.append(
                        select_chain(
                            [g_ij[i][j] for i in range(nm)],
                            m_out[name],
                            sl_in[name][j],
                            width,
                            bool_out,
                        )
                    )

        # route each slave's response back to the granted master
        for name in in_names:
            bool_out, width = _kind(sl_out[name][0])
            for i in range(nm):
                grants_row = [g_ij[i][j] for j in range(ns)]
                if name in ("awready", "wready", "arready"):
                    sel_out = _clone(getattr(masters[0], name))
                    proclist.append(
                        select_chain(grants_row, sl_out[name], sel_out, width, bool_out)
                    )
                    proclist.append(resp_ready(sel_out, m_in[name][i], d_active[i]))
                elif name in ("bvalid", "bresp"):
                    sel_out = _clone(getattr(masters[0], name))
                    proclist.append(
                        select_chain(grants_row, sl_out[name], sel_out, width, bool_out)
                    )
                    default = 1 if name == "bvalid" else RESP_DECERR
                    proclist.append(
                        resp_wr(
                            sel_out,
                            m_in[name][i],
                            d_active[i],
                            d_write[i],
                            True,
                            default,
                        )
                    )
                elif name in ("rvalid", "rresp", "rlast"):
                    sel_out = _clone(getattr(masters[0], name))
                    proclist.append(
                        select_chain(grants_row, sl_out[name], sel_out, width, bool_out)
                    )
                    default = 1 if name in ("rvalid", "rlast") else RESP_DECERR
                    proclist.append(
                        resp_wr(
                            sel_out,
                            m_in[name][i],
                            d_active[i],
                            d_write[i],
                            False,
                            default,
                        )
                    )
                elif name in ("bid", "rid"):
                    is_write = name == "bid"
                    sel_out = _clone(getattr(masters[0], name))
                    orig_sel = _clone(orig_id[0])
                    wr_sel = Signal(bool(0))
                    proclist.append(
                        select_chain(grants_row, sl_out[name], sel_out, width, bool_out)
                    )
                    proclist.append(
                        select_chain(grants_row, orig_id, orig_sel, id_width, False)
                    )
                    proclist.append(select_chain(grants_row, write_r, wr_sel, 0, True))
                    proclist.append(
                        resp_id(sel_out, orig_sel, wr_sel, m_in[name][i], int(is_write))
                    )
                else:
                    proclist.append(
                        select_chain(
                            grants_row, sl_out[name], m_in[name][i], width, bool_out
                        )
                    )

        if ctx.trace.enabled:
            for j in range(ns):
                proclist.append(
                    check_no_contention(
                        ctx.aclk,
                        ctx.aresetn,
                        [g_ij[i][j] for i in range(nm)],
                        label="crossbar",
                        trace=ctx.trace,
                    )
                )

        return proclist


@block
def state_stage(
    clk,
    aresetn,
    active,
    owner,
    write_r,
    orig_id,
    any_req,
    owner_next,
    awv_owner,
    awid_owner,
    arid_owner,
    s_bvalid,
    bready_owner,
    s_rvalid,
    rready_owner,
    s_rlast,
    is_full,
):
    """Per-slave arbitration/transaction state."""

    if is_full:

        @always(clk.posedge)
        def p():
            if not aresetn:
                active.next = 0
                owner.next = 0
                write_r.next = 0
                orig_id.next = 0
            elif not active:
                if any_req:
                    owner.next = owner_next
                    active.next = 1
                    write_r.next = awv_owner
                    if awv_owner:
                        orig_id.next = awid_owner
                    else:
                        orig_id.next = arid_owner
            else:
                done = s_bvalid and bready_owner
                if not done:
                    done = s_rvalid and rready_owner and s_rlast
                if done:
                    active.next = 0

    else:

        @always(clk.posedge)
        def p():
            if not aresetn:
                active.next = 0
                owner.next = 0
            elif not active:
                if any_req:
                    owner.next = owner_next
                    active.next = 1
            else:
                done = s_bvalid and bready_owner
                if not done:
                    done = s_rvalid and rready_owner
                if done:
                    active.next = 0

    return p


@block
def default_stage(
    clk, aresetn, d_active, d_write, m_req, m_sel_any, m_awvalid, m_bready, m_rready
):
    """Per-master default-slave transaction state."""

    @always(clk.posedge)
    def p():
        if not aresetn:
            d_active.next = 0
            d_write.next = 0
        elif not d_active:
            if m_req and (not m_sel_any):
                d_active.next = 1
                d_write.next = m_awvalid
        else:
            done = (d_write and m_bready) or ((not d_write) and m_rready)
            if done:
                d_active.next = 0

    return p
