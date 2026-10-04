"""Shared-bus interconnect with arbitration and address decoding.

Implements ``WB-FR-041`` (multiple masters arbitrated onto one slave-facing
bus, plus address-decoded slaves), ``WB-FR-043`` (parameterised by the port
list and address map) and ``WB-FR-044`` (responses routed to the granted
master).  Supports ``WB-FR-049c`` (the default single strategy for the whole
bus) and consumes the pluggable arbiter and address decoder.

The optional ``ERR``/``RTY``/``LOCK`` signals each get their own process,
created at elaboration only when the bus enables them, so every process body
stays within the MyHDL convertible subset.
"""

from myhdl import Signal, always_comb, block, intbv

from ..arbiter import ArbiterBase, FixedPriorityArbiter
from ..checks import WishboneConfigError
from ..decoder import address_decoder
from .base import InterconnectBase, InterconnectContext

__all__ = ["SharedBus"]


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

        # Pre-extract the per-port signals into plain lists of Signal objects.
        # MyHDL's sensitivity analysis does not resolve subscripts, so reading
        # ``masters[i].cyc`` / ``slaves[i].ack`` inside an @always_comb would
        # not be tracked; indexing a list of signals is tracked correctly.
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

        @block
        def _master_mux():
            @always_comb
            def core():
                s_cyc.next = 0
                s_stb.next = 0
                s_we.next = 0
                s_adr.next = 0
                s_dat_w.next = 0
                s_sel.next = 0
                for i in range(nm):
                    if grants[i]:
                        s_cyc.next = reqs[i]
                        s_stb.next = m_stb[i]
                        s_we.next = m_we[i]
                        s_adr.next = m_adr[i]
                        s_dat_w.next = m_dat_w[i]
                        s_sel.next = m_sel[i]

            procs = [core]

            if lock:

                @always_comb
                def lock_mux():
                    s_lock.next = 0
                    for i in range(nm):
                        if grants[i]:
                            s_lock.next = m_lock[i]

                procs.append(lock_mux)

            return procs

        @block
        def _slave_gate(slave, sel):
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
        def _slave_response():
            @always_comb
            def core():
                s_ack.next = 0
                s_dat_r.next = 0
                for i in range(ns):
                    if selects[i]:
                        s_ack.next = sl_ack[i]
                        s_dat_r.next = sl_dat_r[i]

            procs = [core]

            if err:

                @always_comb
                def err_response():
                    s_err.next = 0
                    for i in range(ns):
                        if selects[i]:
                            s_err.next = sl_err[i]

                procs.append(err_response)

            if rty:

                @always_comb
                def rty_response():
                    s_rty.next = 0
                    for i in range(ns):
                        if selects[i]:
                            s_rty.next = sl_rty[i]

                procs.append(rty_response)

            return procs

        @block
        def _master_gate(m, grant):
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

        insts = [arb, dec, _master_mux(), _slave_response()]
        for i in range(ns):
            insts.append(_slave_gate(slaves[i], selects[i]))
        for i in range(nm):
            insts.append(_master_gate(masters[i], grants[i]))
        return insts
