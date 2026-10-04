"""Point-to-point interconnect.

Implements ``WB-FR-040`` (single master <-> single slave).
"""

from myhdl import always_comb, block

from ..checks import WishboneConfigError
from .base import InterconnectBase, InterconnectContext

__all__ = ["PointToPoint"]


class PointToPoint(InterconnectBase):
    """Connect exactly one master port to exactly one slave port."""

    name = "p2p"

    @block
    def build(self, ctx: InterconnectContext):
        if len(ctx.masters) != 1 or len(ctx.slaves) != 1:
            raise WishboneConfigError(
                f"PointToPoint requires exactly 1 master and 1 slave "
                f"(got {len(ctx.masters)} masters, {len(ctx.slaves)} slaves)"
            )

        m = ctx.masters[0]
        s = ctx.slaves[0]
        err, rty, lock = ctx.err, ctx.rty, ctx.lock

        @always_comb
        def core():
            s.cyc.next = m.cyc
            s.stb.next = m.stb
            s.we.next = m.we
            s.adr.next = m.adr
            s.dat_w.next = m.dat_w
            s.sel.next = m.sel
            m.ack.next = s.ack
            m.dat_r.next = s.dat_r

        proclist = [core]

        if err:

            @always_comb
            def err_glue():
                m.err.next = s.err

            proclist.append(err_glue)

        if rty:

            @always_comb
            def rty_glue():
                m.rty.next = s.rty

            proclist.append(rty_glue)

        if lock:

            @always_comb
            def lock_glue():
                s.lock.next = m.lock

            proclist.append(lock_glue)

        return proclist
