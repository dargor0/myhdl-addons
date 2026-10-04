"""AXI4 outstanding-transaction memory slave (``AX-FR-033``).

``axi_full_slave_oo`` is a memory-backed AXI4 slave that supports **multiple
outstanding reads**: ``AR`` requests are queued (up to *depth*) and the ``R``
bursts are returned in order, each echoing its request's ``RID``.  Writes remain
single-outstanding (``B`` echoes ``BID``); INCR addressing is used.

This complements the single-outstanding :func:`myhdl_addons.axi.axi_full_slave`
and is used by the testbench's outstanding-read BFM.
"""

from __future__ import annotations

from typing import Any

from myhdl import Signal, always, always_comb, block, intbv

__all__ = ["axi_full_slave_oo"]

_W_IDLE, _W_WR, _W_BR = 0, 1, 2
_W_NSTATES = 3


@block
def axi_full_slave_oo(port: Any, depth: int = 4):
    """A memory-backed AXI4 slave with an outstanding read queue.

    Args:
        port: an :class:`AxiSlaveView` for the ``full`` variant.
        depth: number of outstanding read requests that can be queued.
    """
    depth = max(2, int(depth))
    dw = len(port.wdata)
    addr_width = len(port.awaddr)
    id_width = len(port.awid)
    nbytes = dw // 8
    shift = nbytes.bit_length() - 1
    size = getattr(port, "size", None) or 0x100
    words = max(size // nbytes, 1)
    lane_masks = tuple(((1 << 8) - 1) << (b * 8) for b in range(nbytes))
    full_mask = (1 << dw) - 1
    # strobe-to-mask expansion as ROM lookups (tuples of ints): keeps the byte
    # merge inside the clocked process within the convertible subset.
    mask_rom = tuple(
        sum(lane_masks[b] for b in range(nbytes) if (s >> b) & 1)
        for s in range(1 << nbytes)
    )
    keep_rom = tuple(full_mask ^ m for m in mask_rom)
    base = getattr(port, "base", 0) or 0

    mem = [Signal(intbv(0)[dw:]) for _ in range(words)]

    ar_id = [Signal(intbv(0)[id_width:]) for _ in range(depth)]
    ar_idx = [Signal(intbv(0)[addr_width:]) for _ in range(depth)]
    ar_len = [Signal(intbv(0)[8:]) for _ in range(depth)]
    ar_count = Signal(intbv(0, min=0, max=depth + 1))
    ar_head = Signal(intbv(0, min=0, max=depth))
    r_busy = Signal(bool(0))
    r_beat = Signal(intbv(0, min=0, max=256))
    r_id = Signal(intbv(0)[id_width:])
    r_idx = Signal(intbv(0)[addr_width:])
    r_len = Signal(intbv(0)[8:])

    w_state = Signal(intbv(_W_IDLE, min=0, max=_W_NSTATES))
    w_beat = Signal(intbv(0, min=0, max=256))
    w_id = Signal(intbv(0)[id_width:])
    w_idx = Signal(intbv(0)[addr_width:])

    @always_comb
    def outputs():
        port.awready.next = w_state == _W_IDLE
        port.wready.next = w_state == _W_WR
        port.bid.next = w_id
        port.bresp.next = 0
        port.bvalid.next = w_state == _W_BR
        port.arready.next = ar_count < depth
        port.rid.next = r_id
        port.rdata.next = mem[r_idx + r_beat]
        port.rresp.next = 0
        port.rlast.next = r_busy and (r_beat == r_len)
        port.rvalid.next = r_busy

    @always(port.aclk.posedge)
    def read_logic():
        if not port.aresetn:
            ar_count.next = 0
            ar_head.next = 0
            r_busy.next = 0
            r_beat.next = 0
        else:
            enq = port.arvalid and port.arready
            pop = r_busy and port.rready and (r_beat == r_len)
            if enq:
                slot = (ar_head + ar_count) % depth
                ar_id[slot].next = port.arid
                ar_idx[slot].next = (port.araddr - base) >> shift
                ar_len[slot].next = port.arlen
            if not r_busy:
                if ar_count > 0:
                    r_id.next = ar_id[ar_head]
                    r_idx.next = ar_idx[ar_head]
                    r_len.next = ar_len[ar_head]
                    r_beat.next = 0
                    r_busy.next = 1
            elif port.rready:
                if r_beat == r_len:
                    r_busy.next = 0
                    ar_head.next = (ar_head + 1) % depth
                else:
                    r_beat.next = r_beat + 1
            if enq and not pop:
                ar_count.next = ar_count + 1
            elif pop and not enq:
                ar_count.next = ar_count - 1

    @always(port.aclk.posedge)
    def write_logic():
        if not port.aresetn:
            w_state.next = _W_IDLE
            w_beat.next = 0
        elif w_state == _W_IDLE:
            if port.awvalid:
                w_idx.next = (port.awaddr - base) >> shift
                w_id.next = port.awid
                w_beat.next = 0
                w_state.next = _W_WR
        elif w_state == _W_WR:
            if port.wvalid:
                idx = w_idx + w_beat
                mask = mask_rom[int(port.wstrb)]
                keep = keep_rom[int(port.wstrb)]
                mem[idx].next = (mem[idx] & keep) | (port.wdata & mask)
                w_beat.next = w_beat + 1
                if port.wlast:
                    w_state.next = _W_BR
        elif w_state == _W_BR:
            if port.bready:
                w_state.next = _W_IDLE

    return outputs, read_logic, write_logic
