"""AXI simulation-time protocol assertions and contention checks.

Implements ``AX-FR-100`` (VALID/payload stability), ``AX-FR-132`` (the
response/error callback plus contention callbacks for overlapping grants and
ID collisions) and ``AX-FR-134`` (the checkers share one
:class:`~myhdl_addons.bus_common.Trace` with the BFMs, so a single trace
configuration captures transactions and violations consistently).

These monitors are **simulation-only** (non-convertible).  Violations either
raise the corresponding :class:`AxiProtocolError` or, when a *trace* is
supplied, are reported through it first; contention checks default to reporting
without aborting so a testbench can collect them.
"""

from __future__ import annotations

from typing import Any

from myhdl import block, instance

from ..bus_common import ContentionEvent, ErrorEvent, Trace
from .checks import AxiProtocolError

__all__ = [
    "check_burst",
    "check_id_unique",
    "check_last_alignment",
    "check_no_contention",
    "check_valid_stable",
]


def _emit_error(trace: Trace | None, port: str | None, kind: str, detail: str) -> None:
    if trace is not None:
        trace.emit_error(ErrorEvent(port=port, kind=kind, extra={"detail": detail}))


def _emit_contention(trace: Trace | None, port: str | None, detail: str) -> None:
    if trace is not None:
        trace.emit_contention(ContentionEvent(port=port, detail=detail))


@block
def check_valid_stable(
    clk: Any,
    resetn: Any,
    valid: Any,
    ready: Any,
    payloads: Any,
    label: str = "channel",
    trace: Trace | None = None,
    port: str | None = None,
):
    """Assert VALID/payload stability for one AXI channel.

    Args:
        clk, resetn: clock and active-low reset.
        valid, ready: the channel handshake signals.
        payloads: iterable of payload signals (address/id/len/...).
        label: channel label used in error messages.
        trace: optional hook registry; a violating transition is emitted as an
            :class:`ErrorEvent` (``kind="protocol"``) before the error is raised.
        port: optional port name used for hook filtering (defaults to *label*).
    """
    payloads = list(payloads)
    n = len(payloads)
    active = False
    snap = [0] * n

    @instance
    def logic():
        nonlocal active
        while True:
            yield clk.posedge
            if not resetn:
                active = False
            else:
                if active and not valid:
                    msg = f"{label}: VALID withdrawn before READY"
                    _emit_error(trace, port or label, "protocol", msg)
                    raise AxiProtocolError(msg)
                if valid and not ready:
                    if active:
                        for k in range(n):
                            if int(payloads[k]) != snap[k]:
                                msg = (
                                    f"{label}: payload changed while VALID "
                                    f"waits for READY"
                                )
                                _emit_error(trace, port or label, "protocol", msg)
                                raise AxiProtocolError(msg)
                    else:
                        active = True
                        for k in range(n):
                            snap[k] = int(payloads[k])
                else:
                    active = False

    return logic


@block
def check_no_contention(
    clk: Any,
    resetn: Any,
    grants: Any,
    label: str = "fabric",
    trace: Trace | None = None,
    port: str | None = None,
    raise_on_error: bool = False,
):
    """Flag overlapping grants (``AX-FR-132``).

    Emits a :class:`ContentionEvent` (and optionally raises) whenever more than
    one signal in *grants* is asserted in the same cycle, which would mean two
    requesters were granted the same resource.
    """
    signals = list(grants)

    @instance
    def logic():
        while True:
            yield clk.posedge
            if not resetn:
                continue
            count = sum(1 for sig in signals if bool(sig))
            if count > 1:
                detail = f"{label}: {count} concurrent grants"
                _emit_contention(trace, port or label, detail)
                if raise_on_error:
                    raise AxiProtocolError(detail)

    return logic


@block
def check_id_unique(
    clk: Any,
    resetn: Any,
    valid: Any,
    ids: Any,
    label: str = "fabric",
    trace: Trace | None = None,
    port: str | None = None,
    raise_on_error: bool = False,
):
    """Flag ID collisions among concurrently valid requests (``AX-FR-132``).

    Emits a :class:`ContentionEvent` (and optionally raises) when two entries
    of *ids* that are valid in the same cycle carry the same identifier.
    """
    valids = list(valid)
    id_sigs = list(ids)

    @instance
    def logic():
        while True:
            yield clk.posedge
            if not resetn:
                continue
            live = [int(id_sigs[k]) for k in range(len(valids)) if bool(valids[k])]
            if len(live) != len(set(live)):
                detail = f"{label}: ID collision among {live}"
                _emit_contention(trace, port or label, detail)
                if raise_on_error:
                    raise AxiProtocolError(detail)

    return logic


@block
def check_burst(
    clk: Any,
    resetn: Any,
    valid: Any,
    burst: Any,
    size: Any,
    length: Any,
    data_width: int = 32,
    label: str = "aw",
    trace: Trace | None = None,
    port: str | None = None,
):
    """Validate AXI burst attributes (``AX-FR-100``).

    While *valid* is asserted it checks that ``AxBURST`` is legal (not ``3``),
    that ``WRAP`` has an allowed length (2/4/8/16 beats, i.e. ``AxLEN`` in
    ``{1,3,7,15}``) and that ``AxSIZE`` does not exceed the data-bus width.
    """
    max_size = (data_width // 8).bit_length() - 1
    wrap_lengths = (1, 3, 7, 15)

    @instance
    def logic():
        while True:
            yield clk.posedge
            if not resetn or not valid:
                continue
            b = int(burst)
            ln = int(length)
            sz = int(size)
            if b == 3:
                msg = f"{label}: invalid AxBURST=3"
            elif b == 2 and ln not in wrap_lengths:
                msg = f"{label}: WRAP AxLEN must be 1/3/7/15, got {ln}"
            elif sz > max_size:
                msg = f"{label}: AxSIZE {sz} exceeds data bus ({max_size})"
            else:
                continue
            _emit_error(trace, port or label, "protocol", msg)
            raise AxiProtocolError(msg)

    return logic


@block
def check_last_alignment(
    clk: Any,
    resetn: Any,
    valid: Any,
    ready: Any,
    last: Any,
    length: Any,
    label: str = "w",
    trace: Trace | None = None,
    port: str | None = None,
):
    """Assert ``LAST`` is aligned with ``LEN`` (``AX-FR-100``).

    Counts accepted beats and requires ``last`` to be deasserted until the final
    (``AxLEN + 1``-th) beat and asserted exactly there.
    """
    beats = 0

    @instance
    def logic():
        nonlocal beats
        while True:
            yield clk.posedge
            if not resetn:
                beats = 0
            elif valid and ready:
                if beats == int(length):
                    if not last:
                        msg = f"{label}: missing LAST at beat {beats}"
                    else:
                        beats = 0
                        continue
                elif last:
                    msg = f"{label}: premature LAST at beat {beats}"
                else:
                    beats += 1
                    continue
                _emit_error(trace, port or label, "protocol", msg)
                raise AxiProtocolError(msg)

    return logic
