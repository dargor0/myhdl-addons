"""Multiplexers (``IC-FR-060..069``).

Two distinct components: :class:`Mux` (binary index select) and
:class:`OneHotMux` (one-hot / OR-reduce select).  Both are convertible: inputs
are exposed as individual ports ``in0 … in{n-1}`` (a tuple/list of signals is
not convertible by MyHDL), the binary select reuses the balanced
:func:`~myhdl_addons.components.mux_tree.build_mux_tree`, and the one-hot
select is a chain of masked-OR stages.

The two components share their configuration model, port allocation and
registered output stage; only their ``hdl`` datapath differs.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_non_negative,
    check_positive,
    mask,
)
from ..common.reset import make_reset
from ..common.views import SignalView
from .mux_tree import build_mux_tree

__all__ = ["Mux", "OneHotMux"]


def _common_params(width, n, valid, registered, en, reset_value, reset_signal) -> dict:
    """Validate and return the configuration shared by the two muxes."""
    p_width = int(check_positive(width, "width"))
    return {
        "width": p_width,
        "n": int(check_positive(n, "n")),
        "valid": bool(check_bool(valid, "valid")),
        "registered": bool(registered),
        "en": bool(en),
        "reset_value": check_non_negative(reset_value, "reset_value") & mask(p_width),
        "reset_signal": make_reset(reset_signal),
    }


def _common_signals(params: dict) -> dict:
    """Allocate the signals shared by the two muxes (everything but ``sel``)."""
    width = params["width"]
    sig = {f"in{i}": Signal(intbv(0)[width:]) for i in range(params["n"])}
    sig["y"] = Signal(intbv(0)[width:])
    if params["valid"]:
        sig["valid"] = Signal(bool(0))
    if params["registered"]:
        sig["clk"] = Signal(bool(0))
        sig["reset"] = params["reset_signal"]
        if params["en"]:
            sig["en"] = Signal(bool(0))
    return sig


def _register_common(ports, params: dict):
    """Return the registered-stage enable, or ``None`` when ``en`` is disabled."""
    return ports.en if params["en"] else None


@block
def _reg(d, q, clk, reset, en, reset_value):
    """Registered stage (multi-bit): synchronous reset > en-hold > capture."""

    active = int(reset.active)

    if en is None:

        @always(clk.posedge)
        def logic():
            if reset == active:
                q.next = reset_value
            else:
                q.next = d

    else:

        @always(clk.posedge)
        def logic():
            if reset == active:
                q.next = reset_value
            elif en:
                q.next = d

    return logic


@block
def _bool_reg(d, q, clk, reset, en):
    """Registered stage (single bit): synchronous reset > en-hold > capture."""

    active = int(reset.active)

    if en is None:

        @always(clk.posedge)
        def logic():
            if reset == active:
                q.next = False
            else:
                q.next = d

    else:

        @always(clk.posedge)
        def logic():
            if reset == active:
                q.next = False
            elif en:
                q.next = d

    return logic


@block
def onehot_stage(sel, i, first, src, value, dst):
    """One OR-reduce stage for the one-hot mux.

    Adds ``value`` to the running OR when select bit ``i`` is set.  The first
    stage seeds the result from zero (``src`` is then unused).
    """

    if first:

        @always_comb
        def logic():
            if sel[i]:
                dst.next = value
            else:
                dst.next = 0

    else:

        @always_comb
        def logic():
            if sel[i]:
                dst.next = src | value
            else:
                dst.next = src

    return logic


class Mux(ComponentBase):
    """Binary-index multiplexer.

    Args:
        width: data width.
        n: number of inputs.
        default_value: output when ``sel`` is out of range.
        valid: expose the ``valid`` (``sel < n``) output.
        registered: register the output (adds ``clk``/``reset``).
        en: add an output enable when registered.
        reset_value: registered reset value for ``y``.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        width: int,
        n: int,
        default_value: int = 0,
        valid: bool = False,
        registered: bool = False,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        self._params = _common_params(
            width, n, valid, registered, en, reset_value, reset_signal
        )
        self._params["default_value"] = check_non_negative(
            default_value, "default_value"
        ) & mask(self._params["width"])

    @property
    def sel_bits(self) -> int:
        """Width of the ``sel`` port."""
        return max(1, ceil_log2(self._params["n"]))

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        sig = _common_signals(self._params)
        sig["sel"] = Signal(intbv(0, min=0, max=1 << self.sel_bits))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Build the processes onto *ports* and return a list of instances."""
        width = self._params["width"]
        n = self._params["n"]
        default_value = self._params["default_value"]
        valid = self._params["valid"]
        registered = self._params["registered"]
        sel_bits = self.sel_bits

        y_dst = ports.y if not registered else Signal(intbv(0)[width:])
        v_dst = None

        # Balanced select tree over in0..in{n-1}, padded with default_value so
        # every out-of-range sel code resolves to it.
        leaves = [ports[f"in{i}"] for i in range(n)]
        leaves += [default_value] * ((1 << sel_bits) - n)
        proclist = [build_mux_tree(ports.sel, leaves, y_dst, sel_bits, width)]

        if valid:
            v_dst = ports.valid if not registered else Signal(bool(0))

            @always_comb
            def valid_proc():
                if int(ports.sel) < n:
                    v_dst.next = 1
                else:
                    v_dst.next = 0

            proclist.append(valid_proc)

        if registered:
            en_sig = _register_common(ports, self._params)
            proclist.append(
                _reg(
                    y_dst,
                    ports.y,
                    ports.clk,
                    ports.reset,
                    en_sig,
                    self._params["reset_value"],
                )
            )
            if valid:
                proclist.append(
                    _bool_reg(v_dst, ports.valid, ports.clk, ports.reset, en_sig)
                )

        return proclist


class OneHotMux(ComponentBase):
    """One-hot select (OR-reduce) multiplexer.

    Args:
        width: data width.
        n: number of inputs.
        valid: expose a ``valid`` output (any bit set; exactly one if ``strict``).
        strict: ``valid`` requires exactly one select bit (flags multi-hot).
        registered: register the output (adds ``clk``/``reset``).
        en: add an output enable when registered.
        reset_value: registered reset value for ``y``.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        width: int,
        n: int,
        valid: bool = False,
        strict: bool = False,
        registered: bool = False,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        self._params = _common_params(
            width, n, valid, registered, en, reset_value, reset_signal
        )
        self._params["strict"] = bool(check_bool(strict, "strict"))

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        sig = _common_signals(self._params)
        sig["sel"] = Signal(intbv(0)[self._params["n"] :])
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Build the processes onto *ports* and return a list of instances."""
        width = self._params["width"]
        n = self._params["n"]
        valid = self._params["valid"]
        strict = self._params["strict"]
        registered = self._params["registered"]
        sel = ports.sel

        y_dst = ports.y if not registered else Signal(intbv(0)[width:])
        v_dst = None

        # OR-reduce chain: y = OR_i (sel[i] ? in_i : 0)
        proclist = []
        cur = 0
        for i in range(n):
            dst = y_dst if i == n - 1 else Signal(intbv(0)[width:])
            proclist.append(onehot_stage(sel, i, i == 0, cur, ports[f"in{i}"], dst))
            cur = dst

        if valid:
            v_dst = ports.valid if not registered else Signal(bool(0))
            if strict:

                @always_comb
                def valid_proc():
                    if sel != 0:
                        if (sel & (sel - 1)) == 0:
                            v_dst.next = 1
                        else:
                            v_dst.next = 0
                    else:
                        v_dst.next = 0

            else:

                @always_comb
                def valid_proc():
                    if sel != 0:
                        v_dst.next = 1
                    else:
                        v_dst.next = 0

            proclist.append(valid_proc)

        if registered:
            en_sig = _register_common(ports, self._params)
            proclist.append(
                _reg(
                    y_dst,
                    ports.y,
                    ports.clk,
                    ports.reset,
                    en_sig,
                    self._params["reset_value"],
                )
            )
            if valid:
                proclist.append(
                    _bool_reg(v_dst, ports.valid, ports.clk, ports.reset, en_sig)
                )

        return proclist
