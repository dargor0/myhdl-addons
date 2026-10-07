"""RV32I program counter (``RC-FR-029``).

The PC register advances by **4** (32-bit instruction) or **2** (compressed
instruction) each cycle, or loads an arbitrary target (branch/jump result or
trap vector).  Both the sequential advance and the **link value**
(``pc + insn_len``: ``JAL`` -> ``pc+4``, ``c.jal`` -> ``pc+2``) are produced
with the generic :class:`~myhdl_addons.components.Incrementer`; the
branch/jump *target* itself (``pc + imm`` / ``rs1 + imm``) is computed by the
ALU (``RC-FR-029``).
"""

from myhdl import Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    check_non_negative,
    check_positive,
    mask,
)
from ..common.reset import make_reset
from ..common.views import SignalView
from ..components import Incrementer

__all__ = ["ProgramCounter"]

#: Incrementer ``step_sel`` codes: ``0`` -> ``+4``, ``1`` -> ``+2``.
_STEPS = (4, 2)


class ProgramCounter(ComponentBase):
    """RV32I program counter (``RC-FR-029``).

    Ports: ``clk``/``reset``; ``next_pc`` + ``load`` (load the ALU-computed
    target); ``compressed`` (advance/link step is 2 rather than 4); outputs
    ``pc`` and the combinational ``link_value`` (``pc + step``).
    """

    def __init__(
        self, reset_value: int = 0, reset_signal=None, width: int = 32
    ) -> None:
        p_width = int(check_positive(width, "width"))
        self._params = {
            "width": p_width,
            "reset_value": check_non_negative(reset_value, "reset_value")
            & mask(p_width),
            "reset_signal": make_reset(reset_signal),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        return SignalView(
            clk=Signal(bool(0)),
            reset=self._params["reset_signal"],
            next_pc=Signal(intbv(0)[width:]),
            load=Signal(bool(0)),
            compressed=Signal(bool(0)),
            pc=Signal(intbv(0)[width:]),
            link_value=Signal(intbv(0)[width:]),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the program counter onto *ports* and return its instances."""
        width = self._params["width"]
        active = int(self._params["reset_signal"].active)
        reset_value = self._params["reset_value"]

        # Both incrementers are always enabled and select +4/+2 by
        # ``compressed``.  `step_sel` must be an intbv (it drives the
        # incrementer's internal MuxTree) and `en` must be driven (an undriven
        # reg would be x in the converted RTL).
        step_sel = Signal(intbv(0)[1:])
        enabled = Signal(bool(1))

        @always_comb
        def incr_ctrl():
            step_sel.next = ports.compressed
            enabled.next = 1

        next_inc = Incrementer(width=width, steps=_STEPS, load_enable=True)
        next_ports = next_inc.ports()
        next_ports.a = ports.pc
        next_ports.step_sel = step_sel
        next_ports.en = enabled
        next_ports.load = ports.load
        next_ports.load_value = ports.next_pc

        link_inc = Incrementer(width=width, steps=_STEPS, load_enable=False)
        link_ports = link_inc.ports()
        link_ports.a = ports.pc
        link_ports.step_sel = step_sel
        link_ports.en = enabled

        @always(ports.clk.posedge)
        def pc_reg():
            if ports.reset == active:
                ports.pc.next = reset_value
            else:
                ports.pc.next = next_ports.y

        @always_comb
        def link_out():
            ports.link_value.next = link_ports.y

        return [
            next_inc.hdl(next_ports),
            link_inc.hdl(link_ports),
            incr_ctrl,
            pc_reg,
            link_out,
        ]
