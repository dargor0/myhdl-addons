"""Configurable synchronous FIFO (``IC-FR-110..119``).

One component covers buffering and the skid-buffer / register-slice use case:
a skid buffer is ``Fifo(depth=2, interface="stream")``.  The native
``wr_rd`` interface exposes ``wr_en``/``wdata``/``rd_en``/``rdata`` with
``full``/``empty``; the ``stream`` interface exposes a valid/ready face.

Convertibility shapes the implementation: the storage is a memory (list of
signals), occupancy/pointers live in one clocked process, and the read-side
pipeline (head, fall-through/registered data + valid) is a few small
combinational/clocked processes.
"""

from myhdl import ResetSignal, Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_non_negative,
    check_positive,
)
from ..common.reset import make_reset
from ..common.views import SignalView

__all__ = ["INTERFACES", "STREAM", "WR_RD", "Fifo"]

WR_RD = "wr_rd"
STREAM = "stream"
INTERFACES = (WR_RD, STREAM)


@block
def fifo_reset(reset, flush, reset_sig, has_flush):
    """Combine the synchronous reset and optional flush into one reset signal."""
    active = int(reset.active)

    # A single unconditional assignment converts to a continuous `assign`
    # (evaluated at time 0).  An `if/else` would become an edge-sensitive
    # `always @(reset)`, which never fires when reset starts already asserted,
    # leaving `reset_sig` undefined (x) until the first reset transition.
    if has_flush:

        @always_comb
        def p():
            reset_sig.next = (reset == active) or flush

    else:

        @always_comb
        def p():
            reset_sig.next = reset == active

    return p


@block
def fifo_head(mem, rptr, head):
    """Combinational read of the current head word."""

    @always(*mem, rptr)
    def p():
        head.next = mem[rptr]

    return p


@block
def fifo_pre(
    fall_through, empty, head, rdata_reg, rvalid_reg, pre_data, pre_valid, need_valid
):
    """Select the read-side data/valid before the optional output register.

    ``pre_valid`` is only driven in ``stream`` mode, where it is actually
    consumed; otherwise it would be a driven-but-unread signal.
    """

    if not need_valid:
        if fall_through:

            @always_comb
            def p():
                if empty:
                    pre_data.next = rdata_reg
                else:
                    pre_data.next = head

        else:

            @always_comb
            def p():
                pre_data.next = rdata_reg

    elif fall_through:

        @always_comb
        def p():
            if empty:
                pre_data.next = rdata_reg
                pre_valid.next = 0
            else:
                pre_data.next = head
                pre_valid.next = 1

    else:

        @always_comb
        def p():
            pre_data.next = rdata_reg
            pre_valid.next = rvalid_reg

    return p


@block
def fifo_ctrl(
    stream,
    full,
    empty,
    pre_valid,
    wr_en,
    rd_en,
    valid_in,
    ready_out,
    do_wr,
    do_rd,
    ready_in,
):
    """Handshake control: derive ``do_wr``/``do_rd`` and (stream) ``ready_in``."""

    if stream:

        @always_comb
        def p():
            rd = 0
            if pre_valid and ready_out:
                rd = 1
            ri = 0
            if (not full) or rd:
                ri = 1
            do_rd.next = rd
            ready_in.next = ri
            if valid_in and ri:
                do_wr.next = 1
            else:
                do_wr.next = 0

    else:

        @always_comb
        def p():
            if wr_en and (not full):
                do_wr.next = 1
            else:
                do_wr.next = 0
            if rd_en and (not empty):
                do_rd.next = 1
            else:
                do_rd.next = 0

    return p


@block
def fifo_seq(
    mem, clk, reset_sig, do_wr, do_rd, wptr, rptr, used, full, empty, wdata, depth
):
    """Pointer/occupancy/flags update plus the memory write."""

    @always(clk.posedge)
    def p():
        if reset_sig:
            wptr.next = 0
            rptr.next = 0
            used.next = 0
            full.next = 0
            empty.next = 1
        else:
            if do_wr:
                mem[wptr].next = wdata
                wptr.next = (int(wptr) + 1) % depth
            if do_rd:
                rptr.next = (int(rptr) + 1) % depth
            used_next = int(used)
            if do_wr:
                used_next = used_next + 1
            if do_rd:
                used_next = used_next - 1
            used.next = used_next
            if used_next == depth:
                full.next = 1
            else:
                full.next = 0
            if used_next == 0:
                empty.next = 1
            else:
                empty.next = 0

    return p


@block
def fifo_rdreg(
    clk, reset_sig, head, do_rd, rdata_reg, rvalid_reg, fall_through, stream
):
    """Read-data (and stream valid) register."""

    if fall_through:

        @always(clk.posedge)
        def p():
            if reset_sig:
                rdata_reg.next = 0
            else:
                rdata_reg.next = head

    elif stream:

        @always(clk.posedge)
        def p():
            if reset_sig:
                rdata_reg.next = 0
                rvalid_reg.next = 0
            else:
                if do_rd:
                    rdata_reg.next = head
                    rvalid_reg.next = 1
                else:
                    rvalid_reg.next = 0

    else:
        # native (non-fall-through) read: no valid flag is consumed

        @always(clk.posedge)
        def p():
            if reset_sig:
                rdata_reg.next = 0
            else:
                if do_rd:
                    rdata_reg.next = head

    return p


@block
def fifo_outreg(clk, reset_sig, pre_data, pre_valid, out_data, out_valid, need_valid):
    """Optional output register stage (breaks the read path).

    ``out_valid`` is only driven in stream mode, where it is consumed.
    """

    if need_valid:

        @always(clk.posedge)
        def p():
            if reset_sig:
                out_data.next = 0
                out_valid.next = 0
            else:
                out_data.next = pre_data
                if pre_valid:
                    out_valid.next = 1
                else:
                    out_valid.next = 0

    else:

        @always(clk.posedge)
        def p():
            if reset_sig:
                out_data.next = 0
            else:
                out_data.next = pre_data

    return p


@block
def fifo_wire(src, dst):
    """Drive an output port from an internal signal."""

    @always_comb
    def p():
        dst.next = src

    return p


class Fifo(ComponentBase):
    """Synchronous FIFO (``IC-FR-110..119``).

    Args:
        width, depth: geometry (``depth >= 1``).
        interface: ``wr_rd`` (native) or ``stream`` (valid/ready).
        fall_through: first-word-fall-through (combinational) read.
        almost_full, almost_empty: thresholds (``0`` = off).
        count: expose occupancy.
        flush: add a ``flush`` input.
        registered_outputs: add an output register stage.
    """

    def __init__(
        self,
        width: int,
        depth: int,
        interface: str = WR_RD,
        fall_through: bool = False,
        almost_full: int = 0,
        almost_empty: int = 0,
        count: bool = False,
        flush: bool = False,
        registered_outputs: bool = False,
        reset_signal: ResetSignal | None = None,
    ) -> None:
        p_width = check_positive(width, "width")
        p_depth = check_positive(depth, "depth")
        self._params = {
            "width": p_width,
            "depth": p_depth,
            "interface": check_choice(interface, INTERFACES, "interface"),
            "fall_through": check_bool(fall_through, "fall_through"),
            "almost_full": check_non_negative(almost_full, "almost_full"),
            "almost_empty": check_non_negative(almost_empty, "almost_empty"),
            "count": check_bool(count, "count"),
            "flush": check_bool(flush, "flush"),
            "registered_outputs": check_bool(registered_outputs, "registered_outputs"),
            "addr_bits": max(1, ceil_log2(p_depth)),
            "reset_signal": make_reset(reset_signal),
        }

    @property
    def stream(self) -> bool:
        """Whether this FIFO uses the ``stream`` interface."""
        return self._params["interface"] == STREAM

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        sig = {"clk": Signal(bool(0)), "reset": self._params["reset_signal"]}
        if self.stream:
            sig["valid_in"] = Signal(bool(0))
            sig["ready_in"] = Signal(bool(0))
            sig["data_in"] = Signal(intbv(0)[width:])
            sig["valid_out"] = Signal(bool(0))
            sig["ready_out"] = Signal(bool(0))
            sig["data_out"] = Signal(intbv(0)[width:])
        else:
            sig["wr_en"] = Signal(bool(0))
            sig["wdata"] = Signal(intbv(0)[width:])
            sig["rd_en"] = Signal(bool(0))
            sig["rdata"] = Signal(intbv(0)[width:])
            sig["full"] = Signal(bool(0))
            sig["empty"] = Signal(bool(1))
        if self._params["almost_full"]:
            sig["almost_full"] = Signal(bool(0))
        if self._params["almost_empty"]:
            sig["almost_empty"] = Signal(bool(0))
        if self._params["count"]:
            sig["count"] = Signal(intbv(0, min=0, max=self._params["depth"] + 1))
        if self._params["flush"]:
            sig["flush"] = Signal(bool(0))
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the FIFO onto *ports* and return its instances."""
        params = self._params
        width = params["width"]
        depth = params["depth"]
        stream = params["interface"] == STREAM
        fall_through = params["fall_through"]
        registered_outputs = params["registered_outputs"]
        has_flush = params["flush"]
        almost_full = params["almost_full"]
        almost_empty = params["almost_empty"]

        proclist = []
        mem = [Signal(intbv(0)[width:]) for _ in range(depth)]
        wptr = Signal(intbv(0, min=0, max=depth))
        rptr = Signal(intbv(0, min=0, max=depth))
        used = Signal(intbv(0, min=0, max=depth + 1))
        head = Signal(intbv(0)[width:])
        do_wr = Signal(bool(0))
        do_rd = Signal(bool(0))
        reset_sig = Signal(bool(0))
        rdata_reg = Signal(intbv(0)[width:])
        rvalid_reg = None if fall_through else Signal(bool(0))
        pre_data = Signal(intbv(0)[width:])
        pre_valid = Signal(bool(0))

        if stream:
            full_sig = Signal(bool(0))
            empty_sig = Signal(bool(1))
            ready_in = Signal(bool(0))
            wdata = ports.data_in
        else:
            full_sig = ports.full
            empty_sig = ports.empty
            ready_in = None
            wdata = ports.wdata

        proclist.append(
            fifo_reset(
                ports.reset, ports.flush if has_flush else None, reset_sig, has_flush
            )
        )
        proclist.append(fifo_head(mem, rptr, head))
        proclist.append(
            fifo_pre(
                fall_through,
                empty_sig,
                head,
                rdata_reg,
                rvalid_reg,
                pre_data,
                pre_valid,
                stream,
            )
        )
        proclist.append(
            fifo_ctrl(
                stream,
                full_sig,
                empty_sig,
                pre_valid,
                ports.wr_en if not stream else None,
                ports.rd_en if not stream else None,
                ports.valid_in if stream else None,
                ports.ready_out if stream else None,
                do_wr,
                do_rd,
                ready_in,
            )
        )
        proclist.append(
            fifo_seq(
                mem,
                ports.clk,
                reset_sig,
                do_wr,
                do_rd,
                wptr,
                rptr,
                used,
                full_sig,
                empty_sig,
                wdata,
                depth,
            )
        )
        proclist.append(
            fifo_rdreg(
                ports.clk,
                reset_sig,
                head,
                do_rd,
                rdata_reg,
                rvalid_reg,
                fall_through,
                stream,
            )
        )

        if registered_outputs:
            out_data = Signal(intbv(0)[width:])
            out_valid = Signal(bool(0))
            proclist.append(
                fifo_outreg(
                    ports.clk,
                    reset_sig,
                    pre_data,
                    pre_valid,
                    out_data,
                    out_valid,
                    stream,
                )
            )
            data_src = out_data
            valid_src = out_valid
        else:
            data_src = pre_data
            valid_src = pre_valid

        if stream:
            proclist.append(fifo_wire(data_src, ports.data_out))
            proclist.append(fifo_wire(valid_src, ports.valid_out))
            proclist.append(fifo_wire(ready_in, ports.ready_in))
        else:
            proclist.append(fifo_wire(data_src, ports.rdata))

        if self._params["count"]:

            @always_comb
            def count_out():
                ports.count.next = used

            proclist.append(count_out)
        if almost_full:

            @always_comb
            def af_out():
                if int(used) >= almost_full:
                    ports.almost_full.next = 1
                else:
                    ports.almost_full.next = 0

            proclist.append(af_out)
        if almost_empty:

            @always_comb
            def ae_out():
                if int(used) <= almost_empty:
                    ports.almost_empty.next = 1
                else:
                    ports.almost_empty.next = 0

            proclist.append(ae_out)

        return proclist
