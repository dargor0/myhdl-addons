"""AXI4-Stream utility blocks (``AX-FR-052``).

These blocks operate on the simple ``data``/``valid``/``last``/``ready`` signal
convention used by :mod:`myhdl_addons.axi.stream` (the ``last``/``tlast`` signal
carries packet framing):

* :func:`axis_register_slice` -- a one-stage pipeline register with full
  throughput (breaks the downstream-ready to upstream-ready path).
* :func:`axis_gate` -- passes beats only while ``enable`` is asserted.
* :func:`axis_periodic_gate` -- passes beats periodically.
* :func:`axis_width_down` / :func:`axis_width_up` -- width converters
  (downsizer / upsizer).
* :func:`axis_packet_counter` -- counts accepted beats and packets.
"""

from __future__ import annotations

from typing import Any

from myhdl import Signal, always, always_comb, block, intbv

__all__ = [
    "axis_gate",
    "axis_packet_counter",
    "axis_periodic_gate",
    "axis_register_slice",
    "axis_width_down",
    "axis_width_up",
]


@block
def axis_register_slice(
    clk: Any,
    resetn: Any,
    data_in: Any,
    valid_in: Any,
    last_in: Any,
    ready_in: Any,
    data_out: Any,
    valid_out: Any,
    last_out: Any,
    ready_out: Any,
):
    """A one-stage, full-throughput AXI4-Stream pipeline register.

    ``ready_in`` (an output) is asserted whenever the register is empty or the
    downstream is consuming the current beat, so no throughput is lost.  The
    output ``valid`` is registered, so it does not depend combinationally on
    ``valid_in``.
    """
    width = len(data_in)
    data_r = Signal(intbv(0)[width:])
    valid_r = Signal(bool(0))
    last_r = Signal(bool(0))

    @always_comb
    def outputs():
        data_out.next = data_r
        valid_out.next = valid_r
        last_out.next = last_r
        ready_in.next = ready_out or (not valid_r)

    @always(clk.posedge)
    def logic():
        if not resetn:
            valid_r.next = 0
            last_r.next = 0
        elif (not valid_r) or ready_out:
            valid_r.next = valid_in
            last_r.next = last_in
            data_r.next = data_in

    return outputs, logic


@block
def axis_gate(
    data_in: Any,
    valid_in: Any,
    last_in: Any,
    ready_in: Any,
    data_out: Any,
    valid_out: Any,
    last_out: Any,
    ready_out: Any,
    enable: Any,
):
    """Pass beats through only while *enable* is asserted.

    When disabled the beat is dropped and ``ready_in`` is asserted so the
    upstream is not stalled.
    """

    @always_comb
    def logic():
        data_out.next = data_in
        last_out.next = last_in
        valid_out.next = valid_in and enable
        ready_in.next = ready_out or (not enable)

    return logic


@block
def axis_periodic_gate(
    clk: Any,
    resetn: Any,
    data_in: Any,
    valid_in: Any,
    last_in: Any,
    ready_in: Any,
    data_out: Any,
    valid_out: Any,
    last_out: Any,
    ready_out: Any,
    period: int = 2,
):
    """Pass one beat every *period* cycles (periodic throttle)."""
    count = Signal(intbv(0, min=0, max=period))
    tick = Signal(bool(0))

    @always(clk.posedge)
    def counter():
        if not resetn:
            count.next = 0
            tick.next = 0
        elif count >= period - 1:
            count.next = 0
            tick.next = 1
        else:
            count.next = count + 1
            tick.next = 0

    gate = axis_gate(
        data_in,
        valid_in,
        last_in,
        ready_in,
        data_out,
        valid_out,
        last_out,
        ready_out,
        tick,
    )
    return counter, gate


@block
def axis_width_down(
    clk: Any,
    resetn: Any,
    data_in: Any,
    valid_in: Any,
    last_in: Any,
    ready_in: Any,
    data_out: Any,
    valid_out: Any,
    last_out: Any,
    ready_out: Any,
):
    """Downsizer: split each wide input beat into ``n`` narrow output beats.

    ``n = len(data_in) / len(data_out)`` and must be an integer.  ``last`` is
    asserted on the final sub-beat of a packet.
    """
    w_in = len(data_in)
    w_out = len(data_out)
    n = w_in // w_out
    mask = (1 << w_out) - 1

    buf = Signal(intbv(0)[w_in:])
    valid_r = Signal(bool(0))
    last_r = Signal(bool(0))
    sel = Signal(intbv(0, min=0, max=n))

    @always_comb
    def outputs():
        valid_out.next = valid_r
        data_out.next = (buf >> (sel * w_out)) & mask
        last_out.next = last_r and (sel == n - 1)
        ready_in.next = not valid_r

    @always(clk.posedge)
    def logic():
        if not resetn:
            valid_r.next = 0
            last_r.next = 0
            sel.next = 0
        elif not valid_r:
            if valid_in:
                buf.next = data_in
                last_r.next = last_in
                valid_r.next = 1
                sel.next = 0
        elif ready_out:
            if sel == n - 1:
                valid_r.next = 0
                last_r.next = 0
                sel.next = 0
            else:
                sel.next = sel + 1

    return outputs, logic


@block
def axis_width_up(
    clk: Any,
    resetn: Any,
    data_in: Any,
    valid_in: Any,
    last_in: Any,
    ready_in: Any,
    data_out: Any,
    valid_out: Any,
    last_out: Any,
    ready_out: Any,
):
    """Upsizer: combine up to ``n`` narrow input beats into one wide output.

    ``n = len(data_out) / len(data_in)`` and must be an integer.  A wide beat
    is emitted once ``n`` beats have been collected or ``last_in`` arrives.
    """
    w_in = len(data_in)
    w_out = len(data_out)
    n = w_out // w_in
    mask = (1 << w_in) - 1
    full = (1 << w_out) - 1

    buf = Signal(intbv(0)[w_out:])
    valid_r = Signal(bool(0))
    last_r = Signal(bool(0))
    count = Signal(intbv(0, min=0, max=n))

    @always_comb
    def outputs():
        valid_out.next = valid_r
        data_out.next = buf
        last_out.next = last_r
        ready_in.next = not valid_r

    @always(clk.posedge)
    def logic():
        if not resetn:
            valid_r.next = 0
            last_r.next = 0
            count.next = 0
        elif not valid_r:
            if valid_in:
                lane = mask << (count * w_in)
                buf.next = (buf & (full ^ lane)) | ((data_in & mask) << (count * w_in))
                last_r.next = last_in
                if last_in or count == n - 1:
                    valid_r.next = 1
                else:
                    count.next = count + 1
        elif ready_out:
            valid_r.next = 0
            last_r.next = 0
            count.next = 0
            buf.next = 0

    return outputs, logic


@block
def axis_packet_counter(
    clk: Any,
    resetn: Any,
    valid: Any,
    ready: Any,
    last: Any,
    beats: Any,
    packets: Any,
):
    """Count accepted beats and completed packets (``last``)."""

    @always(clk.posedge)
    def logic():
        if not resetn:
            beats.next = 0
            packets.next = 0
        elif valid and ready:
            beats.next = beats + 1
            if last:
                packets.next = packets + 1

    return logic
