"""``tohost``/``fromhost`` interception and halt signature (``RC-FR-111/113``).

The core routes any access whose address matches ``tohost`` or ``fromhost``
here instead of to memory (``hit``), independently of the region map and exempt
from access faults (``RC-FR-111``):

* a **store** to ``tohost`` latches the value as the halt ``signature`` and
  asserts ``halt`` — the standard convention is ``bit0 = 1`` for pass,
  otherwise the exit code is ``value >> 1``;
* a **load** from ``fromhost`` returns the host input ``fromhost_data``;
* ``halt``/``signature`` are sticky until reset, so the testbench can poll them
  to stop the simulation and check the result (``RC-FR-113``).
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, intbv

from ..common.config import ComponentBase, check_non_negative
from ..common.reset import make_reset
from ..common.views import SignalView

__all__ = ["ToHost"]


class ToHost(ComponentBase):
    """tohost/fromhost monitor and sticky halt signature (``RC-FR-111/113``).

    Args:
        tohost_addr, fromhost_addr: the intercepted word addresses.
        reset_signal: reuse a specific ``ResetSignal``, or ``None`` to create one.
    """

    def __init__(
        self,
        tohost_addr: int = 0x1000,
        fromhost_addr: int = 0x1004,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        self._params = {
            "tohost_addr": check_non_negative(tohost_addr, "tohost_addr"),
            "fromhost_addr": check_non_negative(fromhost_addr, "fromhost_addr"),
            "reset_signal": make_reset(reset_signal),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        return SignalView(
            clk=Signal(bool(0)),
            reset=self._params["reset_signal"],
            addr=Signal(intbv(0)[32:]),
            wdata=Signal(intbv(0)[32:]),
            store=Signal(bool(0)),
            load=Signal(bool(0)),
            fromhost_data=Signal(intbv(0)[32:]),
            hit=Signal(bool(0)),
            halt=Signal(bool(0)),
            signature=Signal(intbv(0)[32:]),
            rdata=Signal(intbv(0)[32:]),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the monitor onto *ports* and return its instances."""
        active = int(self._params["reset_signal"].active)
        tohost_addr = self._params["tohost_addr"]
        fromhost_addr = self._params["fromhost_addr"]

        @always_comb
        def hit_proc():
            ports.hit.next = (ports.addr == tohost_addr) or (
                ports.addr == fromhost_addr
            )

        @always_comb
        def load_proc():
            if ports.load and (ports.addr == fromhost_addr):
                ports.rdata.next = ports.fromhost_data
            else:
                ports.rdata.next = 0

        @always(ports.clk.posedge)
        def halt_reg():
            if ports.reset == active:
                ports.halt.next = 0
                ports.signature.next = 0
            elif ports.store and (ports.addr == tohost_addr):
                ports.halt.next = 1
                ports.signature.next = ports.wdata

        return [hit_proc, load_proc, halt_reg]
