"""Multiplexers (``IC-FR-060..069``).

Two distinct components: :class:`Mux` (binary index select) and
:class:`OneHotMux` (one-hot / OR-reduce select).  Both are convertible: a
select process (or an OR-reduce chain) plus an optional registered stage.

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
from ..common.views import SignalView

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
        "reset_signal": reset_signal if isinstance(reset_signal, ResetSignal) else None,
    }


def _common_signals(params: dict) -> dict:
    """Allocate the signals shared by the two muxes (everything but ``sel``)."""
    width = params["width"]
    sig = {
        "inputs": tuple(Signal(intbv(0)[width:]) for _ in range(params["n"])),
        "y": Signal(intbv(0)[width:]),
    }
    if params["valid"]:
        sig["valid"] = Signal(bool(0))
    if params["registered"]:
        sig["clk"] = Signal(bool(0))
        if params["reset_signal"] is None:
            params["reset_signal"] = ResetSignal(0, active=0, isasync=False)
        sig["reset"] = params["reset_signal"]
        if params["en"]:
            sig["en"] = Signal(bool(0))
    return sig


def _register_common(ports, params: dict):
    """Return ``en_sig`` for the registered stage (``Signal(1)`` when no ``en``)."""
    return ports.en if params["en"] else Signal(bool(1))


@block
def _reg(d, q, clk, reset, en, reset_value):
    """Registered stage (multi-bit): reset > en-hold > capture."""

    @always(clk.posedge)
    def logic():
        if not reset:
            if en:
                q.next = d
        else:
            q.next = reset_value

    return logic


@block
def _bool_reg(d, q, clk, reset, en):
    """Registered stage (single bit): reset > en-hold > capture."""

    @always(clk.posedge)
    def logic():
        if not reset:
            if en:
                q.next = d
        else:
            q.next = False

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
        inputs = ports.inputs

        proclist = []
        y_dst = ports.y if not registered else Signal(intbv(0)[width:])
        v_dst = None

        @always(ports.sel, *inputs)
        def mux_proc():
            if int(ports.sel) < n:
                y_dst.next = inputs[int(ports.sel)]
            else:
                y_dst.next = default_value

        proclist.append(mux_proc)

        if valid:
            v_dst = ports.valid if not registered else Signal(bool(0))

            @always_comb
            def valid_proc():
                v_dst.next = 1 if int(ports.sel) < n else 0

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
        inputs = ports.inputs
        sel = ports.sel

        proclist = []
        y_dst = ports.y if not registered else Signal(intbv(0)[width:])
        v_dst = None

        @always(sel, *inputs)
        def onehot_proc():
            result = 0
            for i in range(n):
                if sel[i]:
                    result = result | inputs[i]
            y_dst.next = result

        proclist.append(onehot_proc)

        if valid:
            v_dst = ports.valid if not registered else Signal(bool(0))
            if strict:

                @always_comb
                def valid_proc():
                    v_dst.next = (sel != 0) and ((sel & (sel - 1)) == 0)

            else:

                @always_comb
                def valid_proc():
                    v_dst.next = sel != 0

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
