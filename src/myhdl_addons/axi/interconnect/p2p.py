"""Point-to-point AXI interconnect (``AX-FR-064``).

Connects exactly one master port to exactly one slave port.  Each signal is
assigned explicitly (rather than through a per-signal helper block) so the
converted RTL keeps the real port names and MyHDL does not report spurious
driven/read warnings.  The optional user sidebands are connected only when the
bus enables them.
"""

from __future__ import annotations

from myhdl import always_comb, block

from ..checks import AxiConfigError
from .base import AxiContext, AxiInterconnectBase

__all__ = ["AxiPointToPoint"]


class AxiPointToPoint(AxiInterconnectBase):
    """Connect exactly one master port to exactly one slave port."""

    name = "p2p"

    @block
    def build(self, ctx: AxiContext):
        if len(ctx.masters) != 1 or len(ctx.slaves) != 1:
            raise AxiConfigError(
                "AxiPointToPoint requires exactly 1 master and 1 slave "
                f"(got {len(ctx.masters)} masters, {len(ctx.slaves)} slaves)"
            )

        m = ctx.masters[0]
        s = ctx.slaves[0]
        variant = ctx.variant

        if variant == "stream":

            @always_comb
            def core():
                s.tdata.next = m.tdata
                s.tlast.next = m.tlast
                s.tvalid.next = m.tvalid
                m.tready.next = s.tready

            procs = [core]

            if ctx.user:

                @always_comb
                def user_core():
                    s.tstrb.next = m.tstrb
                    s.tkeep.next = m.tkeep
                    s.tid.next = m.tid
                    s.tdest.next = m.tdest
                    s.tuser.next = m.tuser

                procs.append(user_core)

            return procs

        if variant == "lite":

            @always_comb
            def lite_core():
                s.awaddr.next = m.awaddr
                s.awprot.next = m.awprot
                s.awvalid.next = m.awvalid
                s.wdata.next = m.wdata
                s.wstrb.next = m.wstrb
                s.wvalid.next = m.wvalid
                s.bready.next = m.bready
                s.araddr.next = m.araddr
                s.arprot.next = m.arprot
                s.arvalid.next = m.arvalid
                s.rready.next = m.rready
                m.awready.next = s.awready
                m.wready.next = s.wready
                m.bresp.next = s.bresp
                m.bvalid.next = s.bvalid
                m.arready.next = s.arready
                m.rdata.next = s.rdata
                m.rresp.next = s.rresp
                m.rvalid.next = s.rvalid

            return [lite_core]

        @always_comb
        def full_core():
            s.awid.next = m.awid
            s.awaddr.next = m.awaddr
            s.awlen.next = m.awlen
            s.awsize.next = m.awsize
            s.awburst.next = m.awburst
            s.awlock.next = m.awlock
            s.awcache.next = m.awcache
            s.awprot.next = m.awprot
            s.awvalid.next = m.awvalid
            s.wdata.next = m.wdata
            s.wstrb.next = m.wstrb
            s.wlast.next = m.wlast
            s.wvalid.next = m.wvalid
            s.bready.next = m.bready
            s.arid.next = m.arid
            s.araddr.next = m.araddr
            s.arlen.next = m.arlen
            s.arsize.next = m.arsize
            s.arburst.next = m.arburst
            s.arlock.next = m.arlock
            s.arcache.next = m.arcache
            s.arprot.next = m.arprot
            s.arvalid.next = m.arvalid
            s.rready.next = m.rready
            m.awready.next = s.awready
            m.wready.next = s.wready
            m.bid.next = s.bid
            m.bresp.next = s.bresp
            m.bvalid.next = s.bvalid
            m.arready.next = s.arready
            m.rid.next = s.rid
            m.rdata.next = s.rdata
            m.rresp.next = s.rresp
            m.rlast.next = s.rlast
            m.rvalid.next = s.rvalid

        procs = [full_core]

        if ctx.user:

            @always_comb
            def full_user_core():
                s.awuser.next = m.awuser
                s.aruser.next = m.aruser
                s.wuser.next = m.wuser
                s.awqos.next = m.awqos
                s.arqos.next = m.arqos
                s.awregion.next = m.awregion
                s.arregion.next = m.arregion
                m.buser.next = s.buser
                m.ruser.next = s.ruser

            procs.append(full_user_core)

        return procs
