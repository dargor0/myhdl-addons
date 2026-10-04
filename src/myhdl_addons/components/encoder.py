"""Decoder and priority encoder (``IC-FR-070..078``).

Two distinct components: :class:`Decoder` (binary to one-hot) and
:class:`PriorityEncoder` (bit vector to index).

Both are convertible.  The decoder builds ``1 << sel`` as a chain of small
constant-shift stages (a variable ``1 << sel`` is not expressible in the MyHDL
convertible subset / VHDL); the priority encoder scans the input bits with
indexed bit accesses and a local index variable.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_non_negative,
    check_positive,
    check_registered,
    mask,
)
from ..common.reset import make_reset
from ..common.views import SignalView

__all__ = ["PRIORITIES", "Decoder", "PriorityEncoder"]

PRIORITIES = ("low", "high")


@block
def decode_stage(sel, src, dst, k, amount, full):
    """One decoder stage: shift ``src`` left by ``amount`` when ``sel[k]``.

    ``src`` may be the Python constant ``1`` for the first stage.
    """

    @always_comb
    def step():
        if sel[k]:
            dst.next = (src << amount) & full
        else:
            dst.next = src

    return step


@block
def reg_stage(d, q, clk, reset, reset_value):
    """Registered output stage: synchronous reset clears, otherwise capture."""
    active = int(reset.active)

    @always(clk.posedge)
    def logic():
        if reset == active:
            q.next = reset_value
        else:
            q.next = d

    return logic


@block
def bool_reg(d, q, clk, reset):
    """Single-bit registered output stage (synchronous reset to ``False``)."""
    active = int(reset.active)

    @always(clk.posedge)
    def logic():
        if reset == active:
            q.next = False
        else:
            q.next = d

    return logic


class Decoder(ComponentBase):
    """Binary-to-one-hot decoder (``IC-FR-070..074``).

    Args:
        n: number of outputs.
        en: add a functional ``en`` input (all-zero when low).
        registered: output register latency (``0``/``1``).
        reset_value: registered reset value for ``onehot``.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        n: int,
        en: bool = False,
        registered: int = 0,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_n = check_positive(n, "n")
        p_reset_value = check_non_negative(reset_value, "reset_value")
        p_reset_value &= mask(p_n)
        self._params = {
            "n": p_n,
            "en": check_bool(en, "en"),
            "registered": check_registered(registered),
            "reset_value": p_reset_value,
            "reset_signal": make_reset(reset_signal),
        }

    @property
    def sel_bits(self) -> int:
        """Width of the ``sel`` port."""
        return max(1, ceil_log2(self._params["n"]))

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        n = self._params["n"]
        sig = {
            "sel": Signal(intbv(0, min=0, max=1 << self.sel_bits)),
            "onehot": Signal(intbv(0)[n:]),
        }
        if self._params["en"]:
            sig["en"] = Signal(bool(0))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            sig["reset"] = self._params["reset_signal"]
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the decoder onto *ports* and return its instances."""
        n = self._params["n"]
        registered = self._params["registered"]
        full = mask(n)

        proclist = []
        cur = 1
        for k in range(self.sel_bits):
            nxt = Signal(intbv(0)[n:])
            proclist.append(decode_stage(ports.sel, cur, nxt, k, 1 << k, full))
            cur = nxt
        last = cur

        onehot_dst = ports.onehot if not registered else Signal(intbv(0)[n:])
        if self._params["en"]:

            @always_comb
            def decode_out():
                if ports.en:
                    onehot_dst.next = last
                else:
                    onehot_dst.next = 0

        else:

            @always_comb
            def decode_out():
                onehot_dst.next = last

        proclist.append(decode_out)

        if registered:
            proclist.append(
                reg_stage(
                    onehot_dst,
                    ports.onehot,
                    ports.clk,
                    ports.reset,
                    self._params["reset_value"],
                )
            )

        return proclist


class PriorityEncoder(ComponentBase):
    """Priority encoder (bit vector to index) (``IC-FR-075..078``).

    Args:
        n: number of inputs.
        priority: ``low`` (lowest set bit wins) or ``high``.
        en: add a functional ``en`` input (``valid`` low when deasserted).
        registered: output register latency (``0``/``1``).
        reset_value: registered reset value for ``index``.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        n: int,
        priority: str = "low",
        en: bool = False,
        registered: int = 0,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_n = check_positive(n, "n")
        p_priority = check_choice(priority, PRIORITIES, "priority")
        p_reset_value = check_non_negative(reset_value, "reset_value")
        p_reset_value &= mask(max(1, ceil_log2(p_n)))
        self._params = {
            "n": p_n,
            "priority": p_priority,
            "en": check_bool(en, "en"),
            "registered": check_registered(registered),
            "reset_value": p_reset_value,
            "reset_signal": make_reset(reset_signal),
        }

    @property
    def index_bits(self) -> int:
        """Width of the ``index`` port."""
        return max(1, ceil_log2(self._params["n"]))

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        n = self._params["n"]
        sig = {
            "din": Signal(intbv(0)[n:]),
            "index": Signal(intbv(0)[self.index_bits :]),
            "valid": Signal(bool(0)),
        }
        if self._params["en"]:
            sig["en"] = Signal(bool(0))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            sig["reset"] = self._params["reset_signal"]
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the encoder onto *ports* and return its instances."""
        n = self._params["n"]
        low_first = self._params["priority"] == "low"
        registered = self._params["registered"]

        proclist = []
        index_dst = (
            ports.index if not registered else Signal(intbv(0)[self.index_bits :])
        )
        valid_dst = ports.valid if not registered else Signal(bool(0))

        if low_first:

            @always_comb
            def pick():
                idx = 0
                seen = 0
                for i in range(n):
                    if ports.din[i] and seen == 0:
                        idx = i
                        seen = 1
                index_dst.next = idx

        else:

            @always_comb
            def pick():
                idx = 0
                for i in range(n):
                    if ports.din[i]:
                        idx = i
                index_dst.next = idx

        proclist.append(pick)

        if self._params["en"]:

            @always_comb
            def valid_proc():
                if ports.en:
                    if int(ports.din) != 0:
                        valid_dst.next = 1
                    else:
                        valid_dst.next = 0
                else:
                    valid_dst.next = 0

        else:

            @always_comb
            def valid_proc():
                if int(ports.din) != 0:
                    valid_dst.next = 1
                else:
                    valid_dst.next = 0

        proclist.append(valid_proc)

        if registered:
            proclist.append(
                reg_stage(
                    index_dst,
                    ports.index,
                    ports.clk,
                    ports.reset,
                    self._params["reset_value"],
                )
            )
            proclist.append(bool_reg(valid_dst, ports.valid, ports.clk, ports.reset))

        return proclist
