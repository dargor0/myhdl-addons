"""AXI response status.

The AXI response codes extend the common :class:`~myhdl_addons.bus_common.
records.BusStatus` (``CB-FR-082``/``AX-FR-010``).  Because Python ``Enum``
cannot be subclassed once it has members, the extension is realised as a
superset enum built with :func:`~myhdl_addons.bus_common.extend_bus_status`:
``AxiStatus`` carries every base member (``OK``/``ERROR``/``RETRY``/``DENIED``/
``EXOKAY``) plus the AXI-specific ``OKAY``/``SLVERR``/``DECERR``.
"""

from __future__ import annotations

from enum import Enum

from ..bus_common import BusStatus, extend_bus_status

__all__ = [
    "AXI_TO_BUS",
    "RESP_DECERR",
    "RESP_EXOKAY",
    "RESP_OKAY",
    "RESP_SLVERR",
    "AxiStatus",
    "resp_to_status",
    "status_to_resp",
]

AxiStatus: Enum = extend_bus_status(
    "AxiStatus",
    {"OKAY": "okay", "SLVERR": "slverr", "DECERR": "decerr"},
)

#: Map an AXI status onto the common base status.
AXI_TO_BUS = {
    AxiStatus.OKAY: BusStatus.OK,
    AxiStatus.EXOKAY: BusStatus.EXOKAY,
    AxiStatus.SLVERR: BusStatus.ERROR,
    AxiStatus.DECERR: BusStatus.ERROR,
}

#: Raw ``BRESP``/``RRESP`` encodings.
RESP_OKAY = 0b00
RESP_EXOKAY = 0b01
RESP_SLVERR = 0b10
RESP_DECERR = 0b11

_RESP_TO_STATUS = {
    RESP_OKAY: AxiStatus.OKAY,
    RESP_EXOKAY: AxiStatus.EXOKAY,
    RESP_SLVERR: AxiStatus.SLVERR,
    RESP_DECERR: AxiStatus.DECERR,
}
_STATUS_TO_RESP = {v: k for k, v in _RESP_TO_STATUS.items()}


def resp_to_status(resp: int) -> Enum:
    """Map a raw ``BRESP``/``RRESP`` value to an :class:`AxiStatus`."""
    return _RESP_TO_STATUS.get(int(resp) & 0b11, AxiStatus.DECERR)


def status_to_resp(status: Enum) -> int:
    """Map an :class:`AxiStatus` to the raw ``BRESP``/``RRESP`` encoding."""
    return _STATUS_TO_RESP.get(status, RESP_DECERR)
