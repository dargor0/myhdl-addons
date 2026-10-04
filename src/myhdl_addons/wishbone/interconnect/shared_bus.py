"""Shared-bus interconnect with arbitration and address decoding.

Implements ``WB-FR-041`` (multiple masters arbitrated onto one slave-facing
bus, plus address-decoded slaves), ``WB-FR-043`` (parameterised by the port
list and address map) and ``WB-FR-044`` (responses routed to the granted
master).  Supports ``WB-FR-049c`` (the default single strategy for the whole
bus) and consumes the pluggable arbiter and address decoder.

Convertibility shapes the implementation: a list-of-signals indexed inside a
process is turned by MyHDL into an (invalid) continuously-assigned Verilog
memory, so the one-hot selects drive **elaboration-built chains of per-port
stages** over individual signals instead.
"""

from myhdl import Signal, always_comb, block, intbv

from ...bus_common.muxing import select_chain
from ..arbiter import ArbiterBase, FixedPriorityArbiter
from ..checks import WishboneConfigError
from ..decoder import address_decoder
from .base import InterconnectBase, InterconnectContext

__all__ = ["SharedBus"]


@block
def slave_gate(slave, sel, s_cyc, s_stb, s_we, s_adr, s_dat_w, s_sel, s_lock, lock):
    """Gate the shared bus onto one slave, qualified by its chip-select."""

    @always_comb
    def core():
        slave.cyc.next = s_cyc and sel
        slave.stb.next = s_stb and sel
        slave.we.next = s_we
        slave.adr.next = s_adr
        slave.dat_w.next = s_dat_w
        slave.sel.next = s_sel

    procs = [core]

    if lock:

        @always_comb
        def lock_gate():
            slave.lock.next = s_lock

        procs.append(lock_gate)

    return procs


@block
def master_gate(m, grant, s_ack, s_dat_r, s_err, s_rty, err, rty):
    """Route the shared response back to one master, qualified by its grant."""

    @always_comb
    def core():
        m.ack.next = s_ack and grant
        if grant:
            m.dat_r.next = s_dat_r
        else:
            m.dat_r.next = 0

    procs = [core]

    if err:

        @always_comb
        def err_gate():
            m.err.next = s_err and grant

        procs.append(err_gate)

    if rty:

        @always_comb
        def rty_gate():
            m.rty.next = s_rty and grant

        procs.append(rty_gate)

    return procs


class SharedBus(InterconnectBase):
    """An N-master / M-slave shared bus.

    Args:
        arbiter: an :class:`ArbiterBase` strategy (default: fixed priority).
    """

    name = "shared_bus"

    def __init__(self, arbiter: ArbiterBase | None = None) -> None:
        self.arbiter = arbiter or FixedPriorityArbiter()

    @block
    def build(self, ctx: InterconnectContext):
        nm = len(ctx.masters)
        ns = len(ctx.slaves)
        if nm < 1 or ns < 1:
            raise WishboneConfigError(
                "SharedBus needs at least one master and one slave"
            )

        dw, aw, sw = ctx.data_width, ctx.adr_width, ctx.sel_width
        masters, slaves = ctx.masters, ctx.slaves
        err, rty, lock = ctx.err, ctx.rty, ctx.lock

        # shared slave-facing bus
        s_cyc = Signal(bool(0))
        s_stb = Signal(bool(0))
        s_we = Signal(bool(0))
        s_adr = Signal(intbv(0)[aw:])
        s_dat_w = Signal(intbv(0)[dw:])
        s_sel = Signal(intbv(0)[sw:])
        s_ack = Signal(bool(0))
        s_dat_r = Signal(intbv(0)[dw:])
        s_err = Signal(bool(0)) if err else None
        s_rty = Signal(bool(0)) if rty else None
        s_lock = Signal(bool(0)) if lock else None

        grants = [Signal(bool(0)) for _ in range(nm)]
        selects = [Signal(bool(0)) for _ in range(ns)]

        reqs = [m.cyc for m in masters]
        m_stb = [m.stb for m in masters]
        m_we = [m.we for m in masters]
        m_adr = [m.adr for m in masters]
        m_dat_w = [m.dat_w for m in masters]
        m_sel = [m.sel for m in masters]
        m_lock = [m.lock for m in masters] if lock else []
        sl_ack = [s.ack for s in slaves]
        sl_dat_r = [s.dat_r for s in slaves]
        sl_err = [s.err for s in slaves] if err else []
        sl_rty = [s.rty for s in slaves] if rty else []

        arb = self.arbiter.block(ctx.clk, ctx.rst, reqs, grants)
        dec = address_decoder(
            s_adr, selects, [s.base for s in slaves], [s.size for s in slaves]
        )

        insts = [arb, dec]
        insts.append(select_chain(grants, reqs, s_cyc, 0, True))
        insts.append(select_chain(grants, m_stb, s_stb, 0, True))
        insts.append(select_chain(grants, m_we, s_we, 0, True))
        insts.append(select_chain(grants, m_adr, s_adr, aw, False))
        insts.append(select_chain(grants, m_dat_w, s_dat_w, dw, False))
        insts.append(select_chain(grants, m_sel, s_sel, sw, False))
        if lock:
            insts.append(select_chain(grants, m_lock, s_lock, 0, True))

        insts.append(select_chain(selects, sl_ack, s_ack, 0, True))
        insts.append(select_chain(selects, sl_dat_r, s_dat_r, dw, False))
        if err:
            insts.append(select_chain(selects, sl_err, s_err, 0, True))
        if rty:
            insts.append(select_chain(selects, sl_rty, s_rty, 0, True))

        for i in range(ns):
            insts.append(
                slave_gate(
                    slaves[i],
                    selects[i],
                    s_cyc,
                    s_stb,
                    s_we,
                    s_adr,
                    s_dat_w,
                    s_sel,
                    s_lock,
                    lock,
                )
            )
        for i in range(nm):
            insts.append(
                master_gate(
                    masters[i], grants[i], s_ack, s_dat_r, s_err, s_rty, err, rty
                )
            )
        return insts
