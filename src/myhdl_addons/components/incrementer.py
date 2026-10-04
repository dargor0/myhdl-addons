"""Incrementer / stepper (``IC-FR-040..048``).

A *combinational* stepper that adds one of a set of pre-configured signed
steps (selected by a coded input) to ``a`` and can load an arbitrary value.
Adding two arbitrary operands is the ALU's job.

Convertibility shapes the implementation: the signed step is added in a
``width + 1`` bit field (a two's-complement constant), so the extension bit
doubles as carry/borrow.  One partial result is built per step (so disabling a
step removes its logic) and a small mux selects by ``step_sel``.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, concat, intbv

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
from ..common.errors import HdlConfigError
from ..common.reset import make_reset
from ..common.views import SignalView
from .mux_tree import build_mux_tree

__all__ = ["WRAP_MODES", "Incrementer"]

WRAP_MODES = ("wrap", "saturate")


def _check_steps(steps) -> tuple[int, ...]:
    if steps is None:
        return (1,)
    try:
        values = tuple(steps)
    except TypeError:
        raise HdlConfigError(f"steps must be an iterable of ints, got {steps!r}")
    if not values:
        raise HdlConfigError("steps must not be empty")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise HdlConfigError(f"steps entries must be int, got {value!r}")
    return values


@block
def sum_step(partial_a, ps, step_repr, wide_mask):
    """Add the constant ``step_repr`` (next-width two's complement) to ``a``."""

    @always_comb
    def s():
        ps.next = (partial_a + step_repr) & wide_mask

    return s


@block
def derive_step(ps, py, pc, wrap_mode, sat_val, width, has_carry):
    """Split a step sum into ``y`` (wrap/saturate) and the carry/borrow flag."""

    if wrap_mode == "wrap":
        if has_carry:

            @always_comb
            def d():
                py.next = ps[width:]
                pc.next = ps[width]

        else:

            @always_comb
            def d():
                py.next = ps[width:]

    else:  # saturate
        if has_carry:

            @always_comb
            def d():
                if ps[width]:
                    py.next = sat_val
                else:
                    py.next = ps[width:]
                pc.next = ps[width]

        else:

            @always_comb
            def d():
                if ps[width]:
                    py.next = sat_val
                else:
                    py.next = ps[width:]

    return d


@block
def inc_output(ports, y_dst, carry_dst, y_step, carry_step, has_load, has_carry):
    """Apply the ``load`` / ``en`` priority to the selected step result."""

    if has_load and has_carry:

        @always_comb
        def out():
            if ports.load:
                y_dst.next = ports.load_value
                carry_dst.next = 0
            elif not ports.en:
                y_dst.next = ports.a
                carry_dst.next = 0
            else:
                y_dst.next = y_step
                carry_dst.next = carry_step

    elif has_load:

        @always_comb
        def out():
            if ports.load:
                y_dst.next = ports.load_value
            elif not ports.en:
                y_dst.next = ports.a
            else:
                y_dst.next = y_step

    elif has_carry:

        @always_comb
        def out():
            if not ports.en:
                y_dst.next = ports.a
                carry_dst.next = 0
            else:
                y_dst.next = y_step
                carry_dst.next = carry_step

    else:

        @always_comb
        def out():
            if not ports.en:
                y_dst.next = ports.a
            else:
                y_dst.next = y_step

    return out


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


class Incrementer(ComponentBase):
    """Combinational signed stepper with load and enable (``IC-FR-040..048``).

    Args:
        width: datapath width.
        steps: signed step constants (select width ``ceil(log2 len(steps))``).
        load_enable: provide ``load``/``load_value``.
        wrap_mode: ``wrap`` (modular) or ``saturate`` (clamp to ``[0, 2**w-1]``).
        carry: add the carry/borrow flag output.
        registered: output register latency (``0``/``1``).
        reset_value: registered reset value for ``y``.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        width: int = 32,
        steps=None,
        load_enable: bool = True,
        wrap_mode: str = "wrap",
        carry: bool = False,
        registered: int = 0,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_width = check_positive(width, "width")
        p_reset_value = check_non_negative(reset_value, "reset_value")
        p_reset_value &= mask(p_width)
        self._params = {
            "width": p_width,
            "steps": _check_steps(steps),
            "load_enable": check_bool(load_enable, "load_enable"),
            "wrap_mode": check_choice(wrap_mode, WRAP_MODES, "wrap_mode"),
            "carry": check_bool(carry, "carry"),
            "registered": check_registered(registered),
            "reset_value": p_reset_value,
            "reset_signal": make_reset(reset_signal),
        }

    @property
    def _has_step_sel(self) -> bool:
        return len(self._params["steps"]) > 1

    @property
    def _step_bits(self) -> int:
        steps = self._params["steps"]
        return ceil_log2(len(steps)) if len(steps) > 1 else 0

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        sig = {
            "a": Signal(intbv(0)[width:]),
            "en": Signal(bool(1)),
            "y": Signal(intbv(0)[width:]),
        }
        if self._has_step_sel:
            sig["step_sel"] = Signal(intbv(0, min=0, max=1 << self._step_bits))
        if self._params["load_enable"]:
            sig["load"] = Signal(bool(0))
            sig["load_value"] = Signal(intbv(0)[width:])
        if self._params["carry"]:
            sig["carry"] = Signal(bool(0))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            sig["reset"] = self._params["reset_signal"]
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the stepper onto *ports* and return its instances."""
        width = self._params["width"]
        steps = self._params["steps"]
        load_enable = self._params["load_enable"]
        wrap_mode = self._params["wrap_mode"]
        carry = self._params["carry"]
        registered = self._params["registered"]
        full = mask(width)
        wide = width + 1
        wide_mask = mask(wide)
        nsteps = len(steps)

        proclist = []
        partial_a = Signal(intbv(0)[wide:])

        @always_comb
        def inputentry():
            partial_a.next = concat(intbv(0)[1:], ports.a)

        proclist.append(inputentry)

        partial_y = [Signal(intbv(0)[width:]) for _ in range(nsteps)]
        partial_carry = [Signal(bool(0)) for _ in range(nsteps)] if carry else None

        for k, step in enumerate(steps):
            ps = Signal(intbv(0)[wide:])
            py = partial_y[k]
            pc = partial_carry[k] if carry else None
            step_repr = step & wide_mask
            sat_val = 0 if step < 0 else full
            proclist.append(sum_step(partial_a, ps, step_repr, wide_mask))
            proclist.append(derive_step(ps, py, pc, wrap_mode, sat_val, width, carry))

        if self._has_step_sel:
            # Balanced select tree; out-of-range codes hold ``a`` (y) / 0
            # (carry) by using those values as the padding leaves.
            sel_bits = self._step_bits
            padding = (1 << sel_bits) - nsteps
            y_step = Signal(intbv(0)[width:])
            proclist.append(
                build_mux_tree(
                    ports.step_sel,
                    [*partial_y, *([ports.a] * padding)],
                    y_step,
                    sel_bits,
                    width,
                )
            )
            if carry:
                carry_step = Signal(bool(0))
                proclist.append(
                    build_mux_tree(
                        ports.step_sel,
                        [*partial_carry, *([0] * padding)],
                        carry_step,
                        sel_bits,
                        1,
                    )
                )
            else:
                carry_step = None
        else:
            y_step = partial_y[0]
            carry_step = partial_carry[0] if carry else None

        y_dst = ports.y if not registered else Signal(intbv(0)[width:])
        carry_dst = None
        if carry:
            carry_dst = ports.carry if not registered else Signal(bool(0))
        proclist.append(
            inc_output(ports, y_dst, carry_dst, y_step, carry_step, load_enable, carry)
        )

        if registered:
            proclist.append(
                reg_stage(
                    y_dst,
                    ports.y,
                    ports.clk,
                    ports.reset,
                    self._params["reset_value"],
                )
            )
            if carry:
                proclist.append(
                    bool_reg(carry_dst, ports.carry, ports.clk, ports.reset)
                )

        return proclist
