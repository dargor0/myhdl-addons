"""Balanced-tree multiplexer (``IC-FR-096..099``).

A pure-combinational ``n``-input, ``width``-bit multiplexer built as a
**balanced binary tree of 2:1 muxes**, so its depth is ``ceil(log2 n)`` by
construction.  This is the tool-independent counterpart of the priority-chain
idiom: a cascaded ``if sel == k`` chain only becomes a parallel/balanced mux
when the synthesis tool proves the selects mutually exclusive and restructures
(Yosys does so only with the optional ``muxpack`` pass), whereas ``MuxTree``
fixes the depth in the RTL itself.

Inputs are exposed as individual ports ``in0 … in{n-1}`` (a tuple/list of
signals is not convertible by MyHDL).  When ``n`` is a power of two every
select code maps to a real input; otherwise the unused codes are resolved by a
required **policy** (``const`` / ``lastinput`` / ``alias`` / ``wrap``), which
is also the cheapest choice in terms of resources (``lastinput`` padding
leaves are identical, so they collapse in the tree).
"""

from myhdl import Signal, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_non_negative,
    check_positive,
    mask,
)
from ..common.errors import HdlConfigError
from ..common.views import SignalView

__all__ = ["POLICIES", "MuxTree"]

#: Valid out-of-range select policies (used when ``n`` is not a power of two).
POLICIES = ("const", "lastinput", "alias", "wrap")


@block
def mux2(sel, bit, a, b, out):
    """One balanced-tree node: ``out = b if sel[bit] else a``.

    ``a``/``b`` may be signals or constant ints (padding leaves).
    """

    @always_comb
    def logic():
        if sel[bit]:
            out.next = b
        else:
            out.next = a

    return logic


@block
def build_mux_tree(sel, leaves, out, sel_bits, width):
    """Build a balanced binary tree of 2:1 muxes over *leaves*.

    ``leaves`` is a list of ``2**sel_bits`` values (signals or constants,
    already padded); level ``k`` selects by bit ``k`` of ``sel``.  Identical
    operands (e.g. repeated padding leaves) collapse into no mux.
    """
    level = leaves
    proclist = []
    for bit in range(sel_bits):
        last = bit == sel_bits - 1
        next_level = []
        for j in range(0, len(level), 2):
            a = level[j]
            b = level[j + 1]
            if last:
                proclist.append(mux2(sel, bit, a, b, out))
                next_level.append(out)
            elif a is b:
                next_level.append(a)
            else:
                node = Signal(intbv(0)[width:])
                proclist.append(mux2(sel, bit, a, b, node))
                next_level.append(node)
        level = next_level
    return proclist


class MuxTree(ComponentBase):
    """Balanced binary-tree multiplexer.

    Args:
        width: data width of each input/output.
        n: number of inputs (>= 1).
        policy: how unused select codes resolve when ``n`` is not a power of
            two; one of :data:`POLICIES`.  Required (not ``None``) in that
            case; defaults to ``"lastinput"`` (lowest resource).
        default_value: output for unused codes when ``policy == "const"``.
        alias: input index used for unused codes when ``policy == "alias"``.
    """

    def __init__(
        self,
        width: int = 32,
        n: int = 2,
        policy: str | None = "lastinput",
        default_value: int = 0,
        alias: int = 0,
    ) -> None:
        p_width = int(check_positive(width, "width"))
        p_n = int(check_positive(n, "n"))
        has_holes = (p_n & (p_n - 1)) != 0
        if policy is None:
            if has_holes:
                raise HdlConfigError("policy is required when n is not a power of two")
            p_policy = "lastinput"
        elif policy not in POLICIES:
            raise HdlConfigError(f"policy must be one of {POLICIES}, got {policy!r}")
        else:
            p_policy = policy
        p_alias = check_non_negative(alias, "alias")
        if has_holes and p_policy == "alias" and p_alias >= p_n:
            raise HdlConfigError(f"alias must be in [0, {p_n}), got {p_alias}")
        self._params = {
            "width": p_width,
            "n": p_n,
            "policy": p_policy,
            "default_value": check_non_negative(default_value, "default_value")
            & mask(p_width),
            "alias": p_alias,
        }

    @property
    def sel_bits(self) -> int:
        """Width of the ``sel`` port (``0`` when ``n == 1``)."""
        return ceil_log2(self._params["n"])

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        sig = {f"in{i}": Signal(intbv(0)[width:]) for i in range(self._params["n"])}
        if self.sel_bits:
            sig["sel"] = Signal(intbv(0, min=0, max=1 << self.sel_bits))
        sig["y"] = Signal(intbv(0)[width:])
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Build the balanced mux tree onto *ports* and return its instances."""
        width = self._params["width"]
        n = self._params["n"]
        policy = self._params["policy"]
        default_value = self._params["default_value"]
        alias = self._params["alias"]
        sel_bits = self.sel_bits

        if sel_bits == 0:  # n == 1: a plain wire
            in0 = ports["in0"]

            @always_comb
            def passthrough():
                ports.y.next = in0

            return [passthrough]

        # Leaf level: the real inputs, padded to 2**sel_bits leaves according
        # to the policy (only when n is not a power of two).
        level = [ports[f"in{i}"] for i in range(n)]
        padding = (1 << sel_bits) - n
        if padding:
            if policy == "const":
                level += [default_value] * padding
            elif policy == "alias":
                level += [ports[f"in{alias}"]] * padding
            elif policy == "wrap":
                level += [ports[f"in{j}"] for j in range(padding)]
            else:  # lastinput
                level += [ports[f"in{n - 1}"]] * padding

        return [build_mux_tree(ports.sel, level, ports.y, sel_bits, width)]
