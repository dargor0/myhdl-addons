"""AXI4 (full) memory-backed slave (``AX-FR-030..037``).

A basic single-transaction slave supporting INCR bursts, ``WSTRB`` writes and
``RLAST``/``WLAST``.  For the first release it accepts the write address (AW)
before the write data (W): ``WREADY`` is held low until ``AW`` is captured, so
a master that issues W before AW simply waits (protocol-legal).  AW and AR are
serialized (one transaction at a time).
"""

from __future__ import annotations

from typing import Any

from myhdl import Signal, always, always_comb, block, intbv

__all__ = ["axi_full_slave", "axi_master"]

_IDLE, _WR, _BR, _RD = 0, 1, 2, 3
_NSTATES = 4

_M_IDLE, _M_AW, _M_W, _M_B, _M_AR, _M_R = 0, 1, 2, 3, 4, 5
_M_NSTATES = 6


@block
def axi_full_slave(port: Any):
    """A memory-backed AXI4 slave.

    Args:
        port: an :class:`AxiSlaveView` for the ``full`` variant (``base``/
            ``size`` define the backing memory window).
    """
    dw = len(port.wdata)
    addr_width = len(port.awaddr)
    id_width = len(port.awid)
    nbytes = dw // 8
    shift = nbytes.bit_length() - 1
    size = getattr(port, "size", None) or 0x100
    words = max(size // nbytes, 1)
    base = getattr(port, "base", 0) or 0
    lane_masks = tuple(((1 << 8) - 1) << (b * 8) for b in range(nbytes))
    full_mask = (1 << dw) - 1
    # strobe-to-mask expansion as ROM lookups (tuples of ints) so the byte
    # merge stays inside the clocked process and within the convertible subset.
    mask_rom = tuple(
        sum(lane_masks[b] for b in range(nbytes) if (s >> b) & 1)
        for s in range(1 << nbytes)
    )
    keep_rom = tuple(full_mask ^ m for m in mask_rom)

    mem = [Signal(intbv(0)[dw:]) for _ in range(words)]
    state = Signal(intbv(_IDLE, min=0, max=_NSTATES))
    beat = Signal(intbv(0, min=0, max=256))
    awid_r = Signal(intbv(0)[id_width:])
    awlen_r = Signal(intbv(0)[8:])
    wburst_r = Signal(intbv(0)[2:])
    widx_r = Signal(intbv(0)[addr_width:])
    arid_r = Signal(intbv(0)[id_width:])
    arlen_r = Signal(intbv(0)[8:])
    rburst_r = Signal(intbv(0)[2:])
    ridx_r = Signal(intbv(0)[addr_width:])
    rdata_r = Signal(intbv(0)[dw:])
    # burst word index as a fixed-width signal: a Python local would be
    # re-inferred with a different width per INCR/FIXED/WRAP branch and MyHDL
    # rejects the resulting type mismatch.
    idx = Signal(intbv(0)[addr_width:])

    @always_comb
    def burst_index():
        if state == _RD:
            nxt = beat + 1
            beats = arlen_r + 1
            if rburst_r == 0:
                idx.next = ridx_r
            elif rburst_r == 1:
                idx.next = ridx_r + nxt
            else:
                lower = (ridx_r // beats) * beats
                idx.next = lower + ((ridx_r - lower + nxt) % beats)
        else:
            beats = awlen_r + 1
            if wburst_r == 0:
                idx.next = widx_r
            elif wburst_r == 1:
                idx.next = widx_r + beat
            else:
                lower = (widx_r // beats) * beats
                idx.next = lower + ((widx_r - lower + beat) % beats)

    @always_comb
    def outputs():
        port.awready.next = 0
        port.wready.next = 0
        port.bvalid.next = 0
        port.bid.next = awid_r
        port.bresp.next = 0
        port.arready.next = 0
        port.rvalid.next = 0
        port.rid.next = arid_r
        port.rresp.next = 0
        port.rdata.next = 0
        port.rlast.next = 0
        if state == _IDLE:
            if port.awvalid:
                port.awready.next = 1
            else:
                port.arready.next = 1
        elif state == _WR:
            port.wready.next = 1
        elif state == _BR:
            port.bvalid.next = 1
        elif state == _RD:
            port.rvalid.next = 1
            port.rdata.next = rdata_r
            if beat == arlen_r:
                port.rlast.next = 1

    @always(port.aclk.posedge)
    def fsm():
        if not port.aresetn:
            state.next = _IDLE
            beat.next = 0
        elif state == _IDLE:
            if port.awvalid:
                widx_r.next = (port.awaddr - base) >> shift
                wburst_r.next = port.awburst
                awid_r.next = port.awid
                awlen_r.next = port.awlen
                beat.next = 0
                state.next = _WR
            elif port.arvalid:
                ridx_r.next = (port.araddr - base) >> shift
                rburst_r.next = port.arburst
                arid_r.next = port.arid
                arlen_r.next = port.arlen
                rdata_r.next = mem[(port.araddr - base) >> shift]
                beat.next = 0
                state.next = _RD
        elif state == _WR:
            if port.wvalid:
                mask = mask_rom[int(port.wstrb)]
                keep = keep_rom[int(port.wstrb)]
                mem[idx].next = (mem[idx] & keep) | (port.wdata & mask)
                beat.next = beat + 1
                if port.wlast:
                    state.next = _BR
        elif state == _BR:
            if port.bready:
                state.next = _IDLE
        elif state == _RD:
            if port.rready:
                if beat == arlen_r:
                    state.next = _IDLE
                else:
                    beat.next = beat + 1
                    rdata_r.next = mem[idx]

    return outputs, burst_index, fsm


@block
def axi_master(
    port: Any,
    start: Any,
    write: Any,
    addr: Any,
    length: Any,
    wdata: Any,
    wstrb: Any,
    wvalid: Any,
    wready: Any,
    rdata: Any,
    rvalid: Any,
    rready: Any,
    busy: Any,
    done: Any,
    burst: Any = None,
):
    """A basic AXI4 (full) master with INCR/FIXED/WRAP bursts.

    Write beats are taken from an upstream source (``wdata``/``wstrb``/
    ``wvalid`` -> ``wready``); read beats are pushed downstream (``rdata``/
    ``rvalid`` <- ``rready``).  ``start`` pulses one burst of ``length`` beats.
    ``burst`` optionally supplies the ``AxBURST`` code (default ``INCR``).
    """
    addr_width = len(port.awaddr)
    dw = len(port.wdata)
    size_enc = (dw // 8).bit_length() - 1
    burst_code = 1 if burst is None else int(burst)

    m = Signal(intbv(_M_IDLE, min=0, max=_M_NSTATES))
    addr_r = Signal(intbv(0)[addr_width:])
    len_r = Signal(intbv(0)[8:])
    beat = Signal(intbv(0, min=0, max=256))

    @always_comb
    def outputs():
        port.awaddr.next = addr_r
        port.awlen.next = len_r
        port.awsize.next = size_enc
        port.awburst.next = burst_code
        port.awid.next = 0
        port.awlock.next = 0
        port.awcache.next = 0
        port.awprot.next = 0
        port.wdata.next = wdata
        port.wstrb.next = wstrb
        port.awvalid.next = 0
        port.wvalid.next = 0
        port.wlast.next = 0
        port.bready.next = 0
        port.araddr.next = addr_r
        port.arlen.next = len_r
        port.arsize.next = size_enc
        port.arburst.next = burst_code
        port.arid.next = 0
        port.arlock.next = 0
        port.arcache.next = 0
        port.arprot.next = 0
        port.arvalid.next = 0
        port.rready.next = rready  # asserted early so the slave sees it in RD
        wready.next = 0
        rdata.next = port.rdata
        rvalid.next = 0
        if m == _M_AW:
            port.awvalid.next = 1
        elif m == _M_W:
            port.wvalid.next = wvalid
            wready.next = port.wready
            if beat == len_r:
                port.wlast.next = 1
            else:
                port.wlast.next = 0
        elif m == _M_B:
            port.bready.next = 1
        elif m == _M_AR:
            port.arvalid.next = 1
        elif m == _M_R:
            port.rready.next = rready
            rvalid.next = port.rvalid
        busy.next = m != _M_IDLE
        done.next = (m == _M_B and port.bvalid) or (
            m == _M_R and port.rvalid and rready and port.rlast
        )

    @always(port.aclk.posedge)
    def fsm():
        if not port.aresetn:
            m.next = _M_IDLE
            beat.next = 0
        elif m == _M_IDLE:
            if start:
                addr_r.next = addr
                len_r.next = length - 1
                beat.next = 0
                if write:
                    m.next = _M_AW
                else:
                    m.next = _M_AR
        elif m == _M_AW:
            if port.awready:
                m.next = _M_W
        elif m == _M_W:
            if wvalid and port.wready:
                if beat == len_r:
                    m.next = _M_B
                else:
                    beat.next = beat + 1
        elif m == _M_B:
            if port.bvalid:
                m.next = _M_IDLE
        elif m == _M_AR:
            if port.arready:
                m.next = _M_R
        elif m == _M_R:
            if port.rvalid and rready:
                if port.rlast:
                    m.next = _M_IDLE
                else:
                    beat.next = beat + 1

    return outputs, fsm
