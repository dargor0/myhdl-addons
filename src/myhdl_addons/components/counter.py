"""Sequential counter (``IC-FR-080..088``).

The sequential counterpart of the :class:`Incrementer`: the state register
plus the same step arithmetic.  Equivalent parameters use identical names.

Convertibility shapes the implementation: each configured step gets its own
small combinational process producing the wrapped/saturated next count, and a
mux selects by ``step_sel``; one clocked process registers count/prescaler and
``tick`` is derived from the terminal count.
"""

from myhdl import Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_int,
    check_positive,
)
from ..common.errors import HdlConfigError
from ..common.views import SignalView
from .incrementer import WRAP_MODES, _check_steps

__all__ = ["Counter"]


@block
def counter_step(mode, step, count, nc, lo, hi, span):
    """Combinational next count for one signed step (wrap/saturate)."""

    if mode == "saturate":

        @always_comb
        def p():
            raw = int(count) + step
            if raw < lo:
                nc.next = lo
            elif raw > hi:
                nc.next = hi
            else:
                nc.next = raw

    elif step < 0:

        @always_comb
        def p():
            d = (hi - step) - int(count)
            nc.next = hi - (d % span)

    else:

        @always_comb
        def p():
            d = (int(count) + step) - lo
            nc.next = lo + (d % span)

    return p


@block
def counter_mux(step_sel, partials, hold, step_next, nsteps):
    """Select the active step's next count; out-of-range holds ``count``."""

    @always(step_sel, hold, *partials)
    def p():
        if int(step_sel) < nsteps:
            step_next.next = partials[int(step_sel)]
        else:
            step_next.next = hold

    return p


@block
def counter_loaded(load_value, loaded, lo, hi):
    """Clamp the load value into the counter range."""

    @always_comb
    def p():
        if int(load_value) < lo:
            loaded.next = lo
        elif int(load_value) > hi:
            loaded.next = hi
        else:
            loaded.next = load_value

    return p


@block
def counter_state(
    clk, resetn, en, load, loaded, step_next, count, presc, reset_value, prescaler, load_enable
):
    """Register count (and prescaler) with reset/load/enable priority."""

    if prescaler > 1:

        if load_enable:

            @always(clk.posedge)
            def p():
                if not resetn:
                    count.next = reset_value
                    presc.next = 0
                elif load:
                    count.next = loaded
                    presc.next = 0
                elif en:
                    if presc == prescaler - 1:
                        count.next = step_next
                        presc.next = 0
                    else:
                        presc.next = presc + 1

        else:

            @always(clk.posedge)
            def p():
                if not resetn:
                    count.next = reset_value
                    presc.next = 0
                elif en:
                    if presc == prescaler - 1:
                        count.next = step_next
                        presc.next = 0
                    else:
                        presc.next = presc + 1

    else:

        if load_enable:

            @always(clk.posedge)
            def p():
                if not resetn:
                    count.next = reset_value
                elif load:
                    count.next = loaded
                elif en:
                    count.next = step_next

        else:

            @always(clk.posedge)
            def p():
                if not resetn:
                    count.next = reset_value
                elif en:
                    count.next = step_next

    return p


@block
def counter_tick(count, tick, hi):
    """Combinational tick: asserted while at terminal count."""

    @always_comb
    def p():
        if int(count) == hi:
            tick.next = 1
        else:
            tick.next = 0

    return p


class Counter(ComponentBase):
    """Configurable synchronous counter (``IC-FR-080..088``).

    Args:
        width: counter width.
        steps: signed step values (as in the ``Incrementer``).
        min, max: counter range (default ``0`` .. ``2**width-1``).
        wrap_mode: ``wrap`` (modular) or ``saturate`` (clamp).
        prescaler: divide the input enable.
        load_enable: provide ``load``/``load_value``.
        reset_value: reset count.
        tick: expose the terminal-count ``tick`` output.
    """

    def __init__(
        self,
        width: int = 32,
        steps=None,
        min: int = 0,
        max: int | None = None,
        wrap_mode: str = "wrap",
        prescaler: int = 1,
        load_enable: bool = True,
        reset_value: int = 0,
        tick: bool = True,
    ) -> None:
        p_width = check_positive(width, "width")
        p_min = check_int(min, "min")
        if p_min < 0:
            raise HdlConfigError(f"min must be non-negative, got {min!r}")
        full = (1 << p_width) - 1
        p_max = full if max is None else check_int(max, "max")
        if not (p_min <= p_max <= full):
            raise HdlConfigError(
                f"counter range [{p_min}, {p_max}] must satisfy "
                f"0 <= min <= max <= {full}"
            )
        p_reset_value = check_int(reset_value, "reset_value")
        if not (p_min <= p_reset_value <= p_max):
            raise HdlConfigError(
                f"reset_value {p_reset_value} outside [{p_min}, {p_max}]"
            )
        self._params = {
            "width": p_width,
            "steps": _check_steps(steps),
            "min": p_min,
            "max": p_max,
            "wrap_mode": check_choice(wrap_mode, WRAP_MODES, "wrap_mode"),
            "prescaler": check_positive(prescaler, "prescaler"),
            "load_enable": check_bool(load_enable, "load_enable"),
            "reset_value": p_reset_value,
            "tick": check_bool(tick, "tick"),
        }

    @property
    def width(self) -> int:
        """Counter width."""
        return self._params["width"]

    @property
    def steps(self) -> tuple[int, ...]:
        """Configured signed steps."""
        return self._params["steps"]

    @property
    def min(self) -> int:
        """Lower count bound."""
        return self._params["min"]

    @property
    def max(self) -> int:
        """Upper count bound."""
        return self._params["max"]

    @property
    def wrap_mode(self) -> str:
        """Wrap behaviour (``wrap``/``saturate``)."""
        return self._params["wrap_mode"]

    @property
    def prescaler(self) -> int:
        """Input-enable prescaler."""
        return self._params["prescaler"]

    @property
    def load_enable(self) -> bool:
        """Whether ``load``/``load_value`` are present."""
        return self._params["load_enable"]

    @property
    def tick(self) -> bool:
        """Whether the ``tick`` output is present."""
        return self._params["tick"]

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
            "clk": Signal(bool(0)),
            "resetn": Signal(bool(0)),
            "en": Signal(bool(1)),
            "count": Signal(intbv(self._params["reset_value"])[width:]),
        }
        if self._has_step_sel:
            sig["step_sel"] = Signal(intbv(0, min=0, max=1 << self._step_bits))
        if self._params["load_enable"]:
            sig["load"] = Signal(bool(0))
            sig["load_value"] = Signal(intbv(0)[width:])
        if self._params["tick"]:
            sig["tick"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the counter onto *ports* and return its instances."""
        width = self._params["width"]
        steps = self._params["steps"]
        lo = self._params["min"]
        hi = self._params["max"]
        span = hi - lo + 1
        wrap_mode = self._params["wrap_mode"]
        prescaler = self._params["prescaler"]
        load_enable = self._params["load_enable"]
        reset_value = self._params["reset_value"]
        has_tick = self._params["tick"]

        proclist = []
        count = ports.count
        presc = (
            Signal(intbv(0, min=0, max=prescaler)) if prescaler > 1 else None
        )
        load = ports.load if load_enable else None

        partials = [Signal(intbv(0)[width:]) for _ in steps]
        for k, step in enumerate(steps):
            proclist.append(counter_step(wrap_mode, step, count, partials[k], lo, hi, span))

        if self._has_step_sel:
            step_next = Signal(intbv(0)[width:])
            proclist.append(
                counter_mux(
                    ports.step_sel, tuple(partials), count, step_next, len(steps)
                )
            )
        else:
            step_next = partials[0]

        if load_enable:
            loaded = Signal(intbv(0)[width:])
            proclist.append(counter_loaded(ports.load_value, loaded, lo, hi))
        else:
            loaded = None

        proclist.append(
            counter_state(
                ports.clk,
                ports.resetn,
                ports.en,
                load,
                loaded,
                step_next,
                count,
                presc,
                reset_value,
                prescaler,
                load_enable,
            )
        )

        if has_tick:
            proclist.append(counter_tick(count, ports.tick, hi))

        return proclist
