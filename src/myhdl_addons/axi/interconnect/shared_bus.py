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
-------------------

A list-of-signals indexed inside a process is converted by MyHDL into a Verilog
memory that is then continuously assigned (invalid RTL).  Every shared verdict
is therefore driven by **elaboration-built chains of per-element stages** over
individual signals (see :mod:`myhdl_addons.bus_common.muxing`).
"""

from __future__ import annotations

from myhdl import Signal, always, always_comb, block, intbv

from ...bus_common import address_decoder
from ...bus_common.muxing import (
    fanout_gated,
    fanout_plain,
    grant_chain,
    mresp_gated,
    mresp_plain,
    or_chain,
    select_chain,
)
from ..checks import AxiConfigError
from ..interface import MASTER_OUT, SLAVE_OUT
from ..status import RESP_DECERR
from .base import AxiContext, AxiInterconnectBase

__all__ = ["AxiSharedBus"]

_GATED_OUT = ("awvalid", "wvalid", "arvalid")
_GATED_IN = ("awready", "wready", "arready", "bvalid", "rvalid")


def _clone(sig):
    if isinstance(sig.val, bool):
        return Signal(bool(0))
    return Signal(intbv(0)[len(sig.val) :])


def _kind(sig):
    """Return ``(bool_out, width)`` for a signal."""
    if isinstance(sig.val, bool):
        return True, 0
    return False, len(sig.val)


# -- small elaboration stages ---------------------------------------------


@block
def req_stage(m_awvalid, m_arvalid, req):
    """One master's request: ``awvalid or arvalid``."""

    @always_comb
    def p():
        req.next = m_awvalid or m_arvalid

    return p


@block
def mresp_id(src, grant, orig_id, write_r, is_write, dst):
    """Route a response ID, restoring the granted master's original ID."""

    @always_comb
    def p():
        if grant and (write_r == is_write):
            dst.next = orig_id
        else:
            dst.next = src

    return p


@block
def sel_latch(clk, aresetn, active, selects, sel_latched):
    """Latch one slave's chip-select while idle (holds during a transaction)."""

    @always(clk.posedge)
    def p():
        if not aresetn:
            sel_latched.next = 0
        elif not active:
            sel_latched.next = selects

    return p


@block
def resp_default(sel_out, out, active, sel_any, write_r, is_write, default):
    """Response mux default: selected slave, else a default (DECERR/1)."""

    @always_comb
    def p():
        if active and (not sel_any) and (write_r == is_write):
            out.next = default
        else:
            out.next = sel_out

    return p


@block
def ready_default(sel_out, out, sel_any):
    """Ready mux default: selected slave's ready, else 1 when unselected."""

    @always_comb
    def p():
        if not sel_any:
            out.next = 1
        else:
            out.next = sel_out

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
        any_req = Signal(bool(0))
        owner_next = Signal(intbv(0, min=0, max=nm))
        next_write = Signal(bool(0))
        next_awid = Signal(intbv(0)[id_width:])
        next_arid = Signal(intbv(0)[id_width:])

        dec = address_decoder(
            s_adr, selects, ctx.address_map.bases(), ctx.address_map.sizes()
        )

        proclist = [dec]
        for i in range(nm):
            proclist.append(req_stage(m_awvalid[i], m_arvalid[i], reqs[i]))
        proclist.append(or_chain(reqs, any_req))
        proclist.append(or_chain(sel_latched, sel_any))
        proclist.append(grant_chain(active, owner, reqs, grants))
        proclist.append(
            select_chain(
                grants,
                list(range(nm)),
                owner_next,
                max(1, (nm - 1).bit_length()),
                False,
            )
        )
        proclist.append(select_chain(grants, m_awvalid, next_write, 0, True))
        if is_full:
            proclist.append(select_chain(grants, m_awid, next_awid, id_width, False))
            proclist.append(select_chain(grants, m_arid, next_arid, id_width, False))

        for j in range(ns):
            proclist.append(
                sel_latch(ctx.aclk, ctx.aresetn, active, selects[j], sel_latched[j])
            )

        if is_full:

            @always(ctx.aclk.posedge)
            def state():
                if not ctx.aresetn:
                    active.next = 0
                    owner.next = 0
                    write_r.next = 0
                    orig_id.next = 0
                elif not active:
                    if any_req:
                        owner.next = owner_next
                        active.next = 1
                        write_r.next = next_write
                        if next_write:
                            orig_id.next = next_awid
                        else:
                            orig_id.next = next_arid
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
                elif not active:
                    if any_req:
                        owner.next = owner_next
                        active.next = 1
                        write_r.next = next_write
                else:
                    done = s_bvalid and s_bready
                    if not done:
                        done = s_rvalid and s_rready
                    if done:
                        active.next = 0

        proclist.append(state)

        @always_comb
        def address_mux():
            if s_awvalid:
                s_adr.next = s_adr_aw
            else:
                s_adr.next = s_adr_ar

        proclist.append(address_mux)

        # master mux onto the shared bus
        for name in out_names:
            bool_out, width = _kind(m_out[name][0])
            if is_full and name in ("awid", "arid"):
                proclist.append(
                    select_chain(grants, list(range(nm)), s_out[name], id_width, False)
                )
            else:
                proclist.append(
                    select_chain(grants, m_out[name], s_out[name], width, bool_out)
                )

        # broadcast to the slaves (valids gated by the address decode)
        for name in out_names:
            for j in range(ns):
                if name in _GATED_OUT:
                    proclist.append(
                        fanout_gated(s_out[name], sel_latched[j], sl_in[name][j])
                    )
                else:
                    proclist.append(fanout_plain(s_out[name], sl_in[name][j]))

        # slave response mux back onto the shared bus
        for name in in_names:
            bool_out, width = _kind(sl_out[name][0])
            if name in ("awready", "wready", "arready"):
                sel_out = _clone(getattr(masters[0], name))
                proclist.append(
                    select_chain(sel_latched, sl_out[name], sel_out, width, bool_out)
                )
                proclist.append(ready_default(sel_out, s_in[name], sel_any))
            elif name in ("bvalid", "bresp"):
                sel_out = _clone(getattr(masters[0], name))
                proclist.append(
                    select_chain(sel_latched, sl_out[name], sel_out, width, bool_out)
                )
                default = 1 if name == "bvalid" else RESP_DECERR
                proclist.append(
                    resp_default(
                        sel_out, s_in[name], active, sel_any, write_r, True, default
                    )
                )
            elif name in ("rvalid", "rresp", "rlast"):
                sel_out = _clone(getattr(masters[0], name))
                proclist.append(
                    select_chain(sel_latched, sl_out[name], sel_out, width, bool_out)
                )
                default = 1 if name in ("rvalid", "rlast") else RESP_DECERR
                proclist.append(
                    resp_default(
                        sel_out, s_in[name], active, sel_any, write_r, False, default
                    )
                )
            else:
                proclist.append(
                    select_chain(sel_latched, sl_out[name], s_in[name], width, bool_out)
                )

        # route the shared response back to the masters
        for name in in_names:
            for i in range(nm):
                if name == "bid":
                    proclist.append(
                        mresp_id(
                            s_in[name], grants[i], orig_id, write_r, 1, m_in[name][i]
                        )
                    )
                elif name == "rid":
                    proclist.append(
                        mresp_id(
                            s_in[name], grants[i], orig_id, write_r, 0, m_in[name][i]
                        )
                    )
                elif name in _GATED_IN:
                    proclist.append(mresp_gated(s_in[name], grants[i], m_in[name][i]))
                else:
                    proclist.append(mresp_plain(s_in[name], m_in[name][i]))

        return proclist
