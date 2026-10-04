"""AXI library for MyHDL (AXI4, AXI4-Lite, AXI4-Stream).

Public API::

    from myhdl_addons.axi import (
        Axi, AxiPointToPoint, AxiLiteCSR, AxiLiteBFM,
    )

See ``reqs/02_axi_lib.md`` for the requirement set this package implements.
"""

from .bfm import AxiBFM, AxiLiteBFM
from .checks import AxiConfigError, AxiError, AxiProtocolError, AxiTypeError
from .full import axi_full_slave, axi_master
from .interconnect import (
    AxiContext,
    AxiCrossbar,
    AxiInterconnectBase,
    AxiPointToPoint,
    AxiSharedBus,
)
from .interface import (
    Axi,
    AxiMasterView,
    AxiPort,
    AxiSlavePort,
    AxiSlaveView,
)
from .lite import axi_lite_master
from .oo import axi_full_slave_oo
from .protocol import (
    check_burst,
    check_id_unique,
    check_last_alignment,
    check_no_contention,
    check_valid_stable,
)
from .refmodel import AxiMemModel
from .regfile import AxiLiteCSR, bitfield, bitfield_set
from .status import AxiStatus, resp_to_status, status_to_resp
from .stream import axis_sink, axis_source
from .stream_utils import (
    axis_gate,
    axis_packet_counter,
    axis_periodic_gate,
    axis_register_slice,
    axis_width_down,
    axis_width_up,
)
from .trace import ContentionEvent, ErrorEvent, Trace, TransactionRecord

__all__ = [
    "Axi",
    "AxiBFM",
    "AxiConfigError",
    "AxiContext",
    "AxiCrossbar",
    "AxiError",
    "AxiInterconnectBase",
    "AxiLiteBFM",
    "AxiLiteCSR",
    "AxiMasterView",
    "AxiMemModel",
    "AxiPointToPoint",
    "AxiPort",
    "AxiProtocolError",
    "AxiSharedBus",
    "AxiSlavePort",
    "AxiSlaveView",
    "AxiStatus",
    "AxiTypeError",
    "ContentionEvent",
    "ErrorEvent",
    "Trace",
    "TransactionRecord",
    "axi_full_slave",
    "axi_full_slave_oo",
    "axi_lite_master",
    "axi_master",
    "axis_gate",
    "axis_packet_counter",
    "axis_periodic_gate",
    "axis_register_slice",
    "axis_sink",
    "axis_source",
    "axis_width_down",
    "axis_width_up",
    "bitfield",
    "bitfield_set",
    "check_burst",
    "check_id_unique",
    "check_last_alignment",
    "check_no_contention",
    "check_valid_stable",
    "resp_to_status",
    "status_to_resp",
]
