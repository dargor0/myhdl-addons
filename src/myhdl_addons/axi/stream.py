"""AXI4-Stream source and sink helpers (``AX-FR-050``).

These are thin adapters between simple ``data``/``valid``/``last``/``ready``
signals and an AXI4-Stream port view.  Optional sidebands
(``tstrb``/``tkeep``/``tid``/``tdest``/``tuser``) are pass-through when the
port was created with ``user=True`` (``AX-FR-051``).

An AXI4-Stream port always carries ``tlast``, so the adapters read/write it
unconditionally.
"""

from __future__ import annotations

from typing import Any

from myhdl import always_comb, block

__all__ = ["axis_sink", "axis_sink_sidebands", "axis_source", "axis_source_sidebands"]

_SIDEBANDS = ("tstrb", "tkeep", "tid", "tdest", "tuser")


@block
def axis_source(port: Any, data: Any, valid: Any, last: Any, ready: Any):
    """Drive an AXI4-Stream source port from simple handshake signals."""

    @always_comb
    def logic():
        port.tdata.next = data
        port.tvalid.next = valid
        port.tlast.next = last
        ready.next = port.tready

    return logic


@block
def axis_sink(port: Any, ready: Any, data: Any, valid: Any, last: Any):
    """Sample an AXI4-Stream sink port into simple handshake signals."""

    @always_comb
    def logic():
        port.tready.next = ready
        valid.next = port.tvalid and ready
        data.next = port.tdata
        last.next = port.tlast

    return logic


@block
def axis_tie(src: Any, dst: Any):
    """One-way combinational tie ``dst = src`` (a scalar passthrough)."""

    @always_comb
    def logic():
        dst.next = src

    return logic


@block
def axis_source_sidebands(port: Any, sidebands: dict[str, Any]):
    """Pass optional sideband signals to an AXI4-Stream source port."""
    # one process per present sideband: sidebands may have different widths, so
    # they cannot share a single list (MyHDL rejects mixed-width signal lists).
    return [
        axis_tie(sidebands[n], getattr(port, n)) for n in _SIDEBANDS if hasattr(port, n)
    ]


@block
def axis_sink_sidebands(port: Any, sidebands: dict[str, Any]):
    """Pass optional sideband signals from an AXI4-Stream sink port."""
    return [
        axis_tie(getattr(port, n), sidebands[n]) for n in _SIDEBANDS if hasattr(port, n)
    ]
