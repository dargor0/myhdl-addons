"""Instruction front-end / fetch unit (``RC-FR-043/067/073/104``).

The :class:`FetchUnit` turns a stream of 32-bit memory words into a constant
**decoder interface** — ``instr_valid``, ``instr_data`` (the raw 16/32-bit
instruction), ``instr_pc``, ``instr_compressed`` — plus the ``take``/``flush``
handshake, hiding bus wait states and any 32-bit instruction that **straddles a
word boundary** (``RC-FR-043``).  It is small and pipeline-agnostic: the
downstream stages never see its buffer depth.

Instructions are little-endian (``RC-FR-012``): a word at a 4-byte-aligned
address packs two 16-bit parcels; a 32-bit instruction starting at an odd word
parcel takes its low half from the current word and its high half from the
**next** word (one access away when buffered, two when not).

The configurable ``fetch_buffer`` depth (``RC-FR-043``) is the number of
32-bit words kept fetched ahead of the instruction being assembled:

* ``0`` — no look-ahead: a straddling 32-bit instruction needs a **second bus
  access**;
* ``1`` — keep the next word buffered so a straddle is served without a second
  access (default);
* ``2`` — keep two words buffered (a full word ahead).

The unit keeps a small window of aligned words (slot 0 is the word containing
``pc``, slot 1 the next, and so on) built from **explicit per-slot registers**
— never a list indexed inside a process — and assembles each instruction from
slot 0/1.  Region/permission checks and cross-region straddles
(``RC-FR-077/078``) belong to the memory router that drives the fetch client
port; a bus error is surfaced as a sticky ``fault``.
"""

from myhdl import Signal, always, always_comb, block, concat, intbv

from ..common.config import (
    ComponentBase,
    check_choice,
    check_multiple_of,
    check_non_negative,
    check_positive,
    mask,
)
from ..common.reset import make_reset
from ..common.views import SignalView
from .config import AVAIL_FETCH_BUFFER

__all__ = ["FetchUnit"]


@block
def window_slot(
    clk,
    clear,
    shift,
    fill,
    fill_index,
    index,
    rdata,
    data,
    valid,
    data_hi,
    valid_hi,
    top,
):
    """One word-buffer slot: shift down, or load a freshly fetched word.

    A slot loads the response word when it is the current fill target, else
    shifts the next slot's contents down; the top slot empties on a shift.
    ``index``/``top`` are elaboration-time constants.
    """
    if top:

        @always(clk.posedge)
        def p():
            if clear:
                valid.next = 0
            elif fill and (fill_index == index):
                data.next = rdata
                valid.next = 1
            elif shift:
                valid.next = 0

    else:

        @always(clk.posedge)
        def p():
            if clear:
                valid.next = 0
            elif fill and (fill_index == index):
                data.next = rdata
                valid.next = 1
            elif shift:
                data.next = data_hi
                valid.next = valid_hi

    return p


class FetchUnit(ComponentBase):
    """Instruction fetch front-end with a configurable refill buffer.

    Args:
        width: address/data width (32 for RV32).
        fetch_buffer: word look-ahead depth (``0``, ``1`` or ``2``).
        reset_vector: first instruction address after reset.
        reset_signal: reuse a specific ``ResetSignal``, or ``None``.

    Ports (decoder side): ``instr_valid``, ``instr_data`` (raw instruction),
    ``instr_pc``, ``instr_compressed``, ``take``, ``flush``/``req_pc``,
    ``misaligned`` and sticky ``fault``.

    Ports (memory client, ``RC-FR-104``/Q31): ``mem_req_valid``/
    ``mem_req_addr`` out (the fetch client is read-only) and
    ``mem_resp_valid``/``mem_resp_rdata``/``mem_resp_error`` in, one
    outstanding access at a time.
    """

    def __init__(
        self,
        width: int = 32,
        fetch_buffer: int = 1,
        reset_vector: int = 0,
        reset_signal=None,
    ) -> None:
        p_width = check_positive(width, "width")
        reset_vector = check_non_negative(reset_vector, "reset_vector") & mask(
            p_width
        )
        self._params = {
            "width": p_width,
            "fetch_buffer": check_choice(
                fetch_buffer, AVAIL_FETCH_BUFFER, "fetch_buffer"
            ),
            "reset_vector": check_multiple_of(reset_vector, 2, "reset_vector"),
            "reset_signal": make_reset(reset_signal),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        return SignalView(
            clk=Signal(bool(0)),
            reset=self._params["reset_signal"],
            flush=Signal(bool(0)),
            req_pc=Signal(intbv(0)[width:]),
            take=Signal(bool(0)),
            instr_valid=Signal(bool(0)),
            instr_data=Signal(intbv(0)[width:]),
            instr_pc=Signal(intbv(0)[width:]),
            instr_compressed=Signal(bool(0)),
            misaligned=Signal(bool(0)),
            fault=Signal(bool(0)),
            mem_req_valid=Signal(bool(0)),
            mem_req_addr=Signal(intbv(0)[width:]),
            mem_resp_valid=Signal(bool(0)),
            mem_resp_rdata=Signal(intbv(0)[width:]),
            mem_resp_error=Signal(bool(0)),
        )

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the fetch unit onto *ports* and return its instances."""
        width = self._params["width"]
        depth = self._params["fetch_buffer"]
        reset_vector = self._params["reset_vector"]
        active = int(self._params["reset_signal"].active)
        keep = depth + 1
        slots = max(2, keep)

        pc = Signal(intbv(reset_vector)[width:])
        wbase = Signal(intbv(reset_vector & ~3)[width:])
        fill_ptr = Signal(intbv(reset_vector & ~3)[width:])
        busy = Signal(bool(0))
        drop = Signal(bool(0))

        wd = [Signal(intbv(0)[width:]) for _ in range(slots)]
        wv = [Signal(bool(0)) for _ in range(slots)]
        w0, w1 = wd[0], wd[1]
        v0, v1 = wv[0], wv[1]
        v2 = None
        if slots >= 3:
            v2 = wv[2]

        first = Signal(intbv(0)[16:])
        is32 = Signal(bool(0))
        used = Signal(intbv(0)[3:])
        shift = Signal(bool(0))
        fill = Signal(bool(0))
        fill_index = Signal(intbv(0)[3:])
        clear = Signal(bool(0))
        demand = Signal(bool(0))
        step = Signal(intbv(2)[3:])
        new_pc = Signal(intbv(0)[width:])
        crosses = Signal(bool(0))
        want = Signal(bool(0))

        @always_comb
        def sel_first():
            if pc[1]:
                first.next = w0[32:16]
            else:
                first.next = w0[16:]

        @always_comb
        def detect_length():
            if first[2:] == 3:
                is32.next = 1
            else:
                is32.next = 0

        @always_comb
        def form_data():
            if is32:
                if pc[1]:
                    ports.instr_data.next = concat(w1[16:], w0[32:16])
                else:
                    ports.instr_data.next = w0
            else:
                ports.instr_data.next = first

        @always_comb
        def drive_valid():
            if (not v0) or ports.fault:
                ports.instr_valid.next = 0
            elif (not is32) or (not pc[1]) or v1:
                ports.instr_valid.next = 1
            else:
                ports.instr_valid.next = 0

        @always_comb
        def drive_flags():
            ports.instr_compressed.next = not is32
            ports.instr_pc.next = pc
            ports.misaligned.next = pc[0]

        if slots >= 3:

            @always_comb
            def calc_used():
                used.next = int(v0) + int(v1) + int(v2)

        else:

            @always_comb
            def calc_used():
                used.next = int(v0) + int(v1)

        @always_comb
        def calc_shift():
            if ports.take and ports.instr_valid and crosses:
                shift.next = 1
            else:
                shift.next = 0

        @always_comb
        def calc_fill():
            if busy and ports.mem_resp_valid and (not drop):
                fill.next = 1
            else:
                fill.next = 0

        @always_comb
        def calc_clear():
            if (ports.reset == active) or ports.flush:
                clear.next = 1
            else:
                clear.next = 0

        @always_comb
        def calc_fill_index():
            # ``shift`` consumes the window's first word, so a fetched word
            # fills one slot lower; clamp to 0 for the delta where ``used``
            # reaches 0 while ``shift`` is still asserted.
            if shift and (used > 0):
                fill_index.next = used - 1
            else:
                fill_index.next = used

        @always_comb
        def calc_step():
            if is32:
                step.next = 4
            else:
                step.next = 2

        @always_comb
        def calc_new_pc():
            new_pc.next = pc + step

        @always_comb
        def calc_cross():
            if new_pc[32:2] != wbase[32:2]:
                crosses.next = 1
            else:
                crosses.next = 0

        @always_comb
        def calc_demand():
            # a straddling 32-bit instruction whose second word is not buffered
            if v0 and is32 and pc[1] and (not v1):
                demand.next = 1
            else:
                demand.next = 0

        @always_comb
        def calc_want():
            if (ports.reset == active) or ports.flush or ports.fault:
                want.next = 0
            elif (not busy) and (not drop) and ((used < keep) or demand):
                want.next = 1
            else:
                want.next = 0

        @always_comb
        def drive_req():
            ports.mem_req_valid.next = want
            ports.mem_req_addr.next = fill_ptr

        @always(ports.clk.posedge)
        def state():
            if ports.reset == active:
                busy.next = 0
                drop.next = 0
                ports.fault.next = 0
                pc.next = reset_vector
                wbase.next = reset_vector & ~3
                fill_ptr.next = reset_vector & ~3
            elif ports.flush:
                ports.fault.next = 0
                pc.next = ports.req_pc
                wbase.next = concat(ports.req_pc[32:2], intbv(0)[2:])
                fill_ptr.next = concat(ports.req_pc[32:2], intbv(0)[2:])
                if busy and (not ports.mem_resp_valid):
                    # keep draining the in-flight read, then drop its response
                    drop.next = 1
                    busy.next = 1
                else:
                    drop.next = 0
                    busy.next = 0
            else:
                if busy and ports.mem_resp_valid:
                    busy.next = 0
                    if drop:
                        drop.next = 0
                    else:
                        if ports.mem_resp_error:
                            ports.fault.next = 1
                        fill_ptr.next = fill_ptr + 4
                if want:
                    busy.next = 1
                if ports.take and ports.instr_valid:
                    if crosses:
                        wbase.next = wbase + 4
                    pc.next = new_pc

        proclist = []
        for index in range(slots):
            top = index == slots - 1
            data_hi = wd[index] if top else wd[index + 1]
            valid_hi = wv[index] if top else wv[index + 1]
            proclist.append(
                window_slot(
                    ports.clk,
                    clear,
                    shift,
                    fill,
                    fill_index,
                    index,
                    ports.mem_resp_rdata,
                    wd[index],
                    wv[index],
                    data_hi,
                    valid_hi,
                    top,
                )
            )

        return [
            *proclist,
            sel_first,
            detect_length,
            form_data,
            drive_valid,
            drive_flags,
            calc_used,
            calc_shift,
            calc_fill,
            calc_clear,
            calc_fill_index,
            calc_step,
            calc_new_pc,
            calc_cross,
            calc_demand,
            calc_want,
            drive_req,
            state,
        ]
