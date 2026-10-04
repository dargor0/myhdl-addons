"""Convertible mux/fanout helpers over one-hot signal lists.

A list of signals indexed inside a process is turned by MyHDL into a Verilog
memory that is then continuously assigned -- something iverilog rejects and
Yosys warns about.  These helpers instead drive scalar signals from one-hot
lists with **elaboration-built chains of per-element stages** over individual
signals, which stays in the convertible subset.
"""

from myhdl import Signal, always_comb, block, intbv

__all__ = [
    "fanout_gated",
    "fanout_plain",
    "grant_chain",
    "grant_first",
    "grant_last",
    "grant_single",
    "grant_stage",
    "mresp_gated",
    "mresp_plain",
    "onehot_first",
    "onehot_stage",
    "or_chain",
    "or_first",
    "or_stage",
    "select_chain",
]


@block
def onehot_first(grant, value, out):
    """First stage: ``out = value if grant else 0``."""

    @always_comb
    def p():
        if grant:
            out.next = value
        else:
            out.next = 0

    return p


@block
def onehot_stage(grant, value, acc, out):
    """Later stage: ``out = value if grant else acc`` (selects are one-hot)."""

    @always_comb
    def p():
        if grant:
            out.next = value
        else:
            out.next = acc

    return p


@block
def select_chain(grants, values, out, width, bool_out):
    """Priority chain selecting ``values`` by one-hot ``grants``.

    ``width`` sizes the intermediate signals when ``bool_out`` is false.
    """
    procs = []
    acc = None
    n = len(values)
    for i in range(n):
        if i == n - 1:
            dst = out
        else:
            dst = Signal(bool(0)) if bool_out else Signal(intbv(0)[width:])
        if i == 0:
            procs.append(onehot_first(grants[i], values[i], dst))
        else:
            procs.append(onehot_stage(grants[i], values[i], acc, dst))
        acc = dst
    return procs


@block
def fanout_gated(src, sel, dst):
    """``dst = src and sel`` for one slot of a gated broadcast."""

    @always_comb
    def p():
        dst.next = src and sel

    return p


@block
def fanout_plain(src, dst):
    """``dst = src`` for one slot of a plain broadcast."""

    @always_comb
    def p():
        dst.next = src

    return p


@block
def mresp_gated(src, grant, dst):
    """``dst = src and grant`` for one master of a gated response fanout."""

    @always_comb
    def p():
        dst.next = src and grant

    return p


@block
def mresp_plain(src, dst):
    """``dst = src`` for one master of a plain response fanout."""

    @always_comb
    def p():
        dst.next = src

    return p


@block
def or_first(bit, out):
    """First OR stage."""

    @always_comb
    def p():
        out.next = bit

    return p


@block
def or_stage(bit, acc, out):
    """Later OR stage."""

    @always_comb
    def p():
        out.next = acc or bit

    return p


@block
def or_chain(bits, out):
    """Elaboration-built OR reduction of the signal list ``bits`` into ``out``."""
    procs = []
    acc = None
    n = len(bits)
    for i in range(n):
        dst = out if i == n - 1 else Signal(bool(0))
        if i == 0:
            procs.append(or_first(bits[i], dst))
        else:
            procs.append(or_stage(bits[i], acc, dst))
        acc = dst
    return procs


@block
def grant_single(active, owner, i, req, grant):
    """Only-requester grant: owner while active, else the request."""

    @always_comb
    def p():
        grant.next = (active and (owner == i)) or ((not active) and req)

    return p


@block
def grant_first(active, owner, i, req, grant, higher):
    """First grant stage: owner while active, else the request."""

    @always_comb
    def p():
        grant.next = (active and (owner == i)) or ((not active) and req)
        higher.next = req

    return p


@block
def grant_stage(active, owner, i, req, higher, grant, higher_next):
    """Middle grant stage: owner while active, else the first requester."""

    @always_comb
    def p():
        grant.next = (active and (owner == i)) or (
            (not active) and req and (not higher)
        )
        higher_next.next = higher or req

    return p


@block
def grant_last(active, owner, i, req, higher, grant):
    """Last grant stage: owner while active, else the first requester."""

    @always_comb
    def p():
        grant.next = (active and (owner == i)) or (
            (not active) and req and (not higher)
        )

    return p


@block
def grant_chain(active, owner, reqs, grants):
    """One-hot grant: the owner while active, else the lowest-index requester."""
    procs = []
    higher = None
    n = len(reqs)
    for i in range(n):
        if i == n - 1:
            if i == 0:
                procs.append(grant_single(active, owner, i, reqs[i], grants[i]))
            else:
                procs.append(grant_last(active, owner, i, reqs[i], higher, grants[i]))
        else:
            higher_next = Signal(bool(0))
            if i == 0:
                procs.append(
                    grant_first(active, owner, i, reqs[i], grants[i], higher_next)
                )
            else:
                procs.append(
                    grant_stage(
                        active, owner, i, reqs[i], higher, grants[i], higher_next
                    )
                )
            higher = higher_next
    return procs
