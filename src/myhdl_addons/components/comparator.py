"""Comparator (``IC-FR-050..056``).

Produces a selectable subset of the comparison flags ``eq, ne, lt, ltu, gt,
gtu, ge, le``.  ``signed`` selects whether ``lt``/``gt``/``ge``/``le`` use
two's-complement comparison; ``ltu``/``gtu`` are always unsigned.

Convertible: one ``@always_comb`` process per enabled flag (created at
elaboration, so disabling a flag removes its logic), plus an optional
registered output stage.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    check_bool,
    check_positive,
    normalize_subset,
)
from ..common.reset import make_reset
from ..common.views import SignalView

__all__ = ["AVAIL_OUTPUTS", "Comparator"]

AVAIL_OUTPUTS = ("eq", "ne", "lt", "ltu", "gt", "gtu", "ge", "le")


class Comparator(ComponentBase):
    """Combinational (or registered) comparison-flag generator.

    Args:
        width: operand width.
        outputs: enabled flag subset (default: all of ``AVAIL_OUTPUTS``).
        signed: signed comparison for ``lt``/``gt``/``ge``/``le``.
        registered: register the flags (adds ``clk``/``reset``).
        en: add an output enable when registered.
        reset_value: registered reset value for the flags.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        width: int = 32,
        outputs=None,
        signed: bool = True,
        registered: bool = False,
        en: bool = False,
        reset_value: int = 0,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_width = int(check_positive(width, "width"))
        p_outputs = normalize_subset(
            outputs, AVAIL_OUTPUTS, "outputs", default=AVAIL_OUTPUTS
        )
        self._params = {
            "width": p_width,
            "outputs": p_outputs,
            "signed": bool(check_bool(signed, "signed")),
            "registered": bool(registered),
            "en": bool(en),
            "reset_value": reset_value,
            "reset_signal": make_reset(reset_signal),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        sig = {
            "a": Signal(intbv(0)[self._params["width"] :]),
            "b": Signal(intbv(0)[self._params["width"] :]),
        }
        for name in self._params["outputs"]:
            sig[name] = Signal(bool(0))
        if self._params["registered"]:
            sig["clk"] = Signal(bool(0))
            sig["reset"] = self._params["reset_signal"]
            if self._params["en"]:
                sig["en"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Build the processes onto *ports* and return a list of instances."""
        width = self._params["width"]
        outputs = self._params["outputs"]
        signed = self._params["signed"]
        registered = self._params["registered"]

        proclist = []

        # Destination of each combinational process: the port itself, or an
        # internal partial signal when a registered stage follows.
        dst = {}
        for name in outputs:
            dst[name] = Signal(bool(0)) if registered else ports[name]

        if "eq" in outputs:
            eq_dst = dst["eq"]

            @always_comb
            def eq_proc():
                eq_dst.next = ports.a == ports.b

            proclist.append(eq_proc)

        if "ne" in outputs:
            ne_dst = dst["ne"]

            @always_comb
            def ne_proc():
                ne_dst.next = ports.a != ports.b

            proclist.append(ne_proc)

        if "ltu" in outputs:
            ltu_dst = dst["ltu"]

            @always_comb
            def ltu_proc():
                ltu_dst.next = ports.a < ports.b

            proclist.append(ltu_proc)

        if "gtu" in outputs:
            gtu_dst = dst["gtu"]

            @always_comb
            def gtu_proc():
                gtu_dst.next = ports.a > ports.b

            proclist.append(gtu_proc)

        if "lt" in outputs:
            lt_dst = dst["lt"]
            if signed:

                @always_comb
                def lt_proc():
                    if ports.a[width - 1] != ports.b[width - 1]:
                        lt_dst.next = ports.a[width - 1]
                    else:
                        lt_dst.next = ports.a < ports.b

            else:

                @always_comb
                def lt_proc():
                    lt_dst.next = ports.a < ports.b

            proclist.append(lt_proc)

        if "gt" in outputs:
            gt_dst = dst["gt"]
            if signed:

                @always_comb
                def gt_proc():
                    if ports.a[width - 1] != ports.b[width - 1]:
                        gt_dst.next = ports.b[width - 1]
                    else:
                        gt_dst.next = ports.a > ports.b

            else:

                @always_comb
                def gt_proc():
                    gt_dst.next = ports.a > ports.b

            proclist.append(gt_proc)

        if "ge" in outputs:
            ge_dst = dst["ge"]
            if signed:

                @always_comb
                def ge_proc():
                    if ports.a[width - 1] != ports.b[width - 1]:
                        ge_dst.next = ports.b[width - 1]
                    else:
                        ge_dst.next = ports.a >= ports.b

            else:

                @always_comb
                def ge_proc():
                    ge_dst.next = ports.a >= ports.b

            proclist.append(ge_proc)

        if "le" in outputs:
            le_dst = dst["le"]
            if signed:

                @always_comb
                def le_proc():
                    if ports.a[width - 1] != ports.b[width - 1]:
                        le_dst.next = ports.a[width - 1]
                    else:
                        le_dst.next = ports.a <= ports.b

            else:

                @always_comb
                def le_proc():
                    le_dst.next = ports.a <= ports.b

            proclist.append(le_proc)

        if registered:
            en_sig = ports.en if self._params["en"] else None
            for name in outputs:
                proclist.append(
                    _bool_reg(ports[name], dst[name], ports.clk, ports.reset, en_sig)
                )

        return proclist


@block
def _bool_reg(q, d, clk, reset, en):
    """Single-bit registered stage: synchronous reset > en-hold > capture.

    The reset polarity follows ``reset.active``; ``en is None`` builds a stage
    with no enable.
    """
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
