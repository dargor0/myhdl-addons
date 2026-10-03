"""Synchronous memories (``IC-FR-100..107``, ``IC-FR-140..144``).

:class:`SyncRam` is a read/write memory; :class:`SyncRom` is a read-only
memory initialised from a required image.  Both support configurable read
latency (``read_latency`` plus an optional ``output_register`` stage, giving
a total latency of ``read_latency + output_register``).

The storage and read/write helpers are shared with
:mod:`~myhdl_addons.components.regfile` (``rf_base``/``rf_bypass``/
``rf_capture``/``rf_wr_port``/…), so both memories stay convertible.
"""

from myhdl import Signal, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_int,
    check_non_negative,
    check_positive,
    check_registered,
    mask,
)
from ..common.errors import HdlConfigError
from ..common.views import SignalView
from .regfile import (
    NO_CHANGE,
    READ_FIRST,
    WRITE_FIRST,
    WRITE_MODES,
    rf_base,
    rf_blocked,
    rf_bypass,
    rf_capture,
    rf_lane,
    rf_old,
    rf_wr_port,
)

__all__ = ["SyncRam", "SyncRom"]


def _check_init(init, depth: int, required: bool) -> tuple[int, ...]:
    if init is None:
        if required:
            raise HdlConfigError("init image is required")
        return tuple(0 for _ in range(depth))
    values = tuple(init)
    if len(values) != depth:
        raise HdlConfigError(f"init image length {len(values)} != depth {depth}")
    for value in values:
        check_non_negative(value, "init entry")
    return values


class SyncRam(ComponentBase):
    """Simple/true dual-port synchronous RAM (``IC-FR-100..107``).

    Args:
        width, depth: geometry.
        read_latency: ``0`` combinational read, ``1`` registered read.
        write_mode: same-address behaviour.
        read_ports, write_ports: port counts.
        byte_write: ``0`` (off) or ``width/8`` (per-lane strobes).
        init: optional initialisation image.
        output_register: extra output register stage.
    """

    def __init__(
        self,
        width: int,
        depth: int,
        read_latency: int = 1,
        write_mode: str = READ_FIRST,
        read_ports: int = 1,
        write_ports: int = 1,
        byte_write: int = 0,
        init=None,
        output_register: bool = False,
    ) -> None:
        p_width = check_positive(width, "width")
        p_depth = check_positive(depth, "depth")
        p_byte_write = check_int(byte_write, "byte_write")
        lanes = p_width // 8
        if p_byte_write not in (0, lanes) or (p_byte_write and p_width % 8 != 0):
            raise HdlConfigError(
                f"byte_write must be 0 or width/8 ({lanes}), got {byte_write!r}"
            )
        self._params = {
            "width": p_width,
            "depth": p_depth,
            "read_latency": check_registered(read_latency, "read_latency"),
            "write_mode": check_choice(write_mode, WRITE_MODES, "write_mode"),
            "read_ports": check_positive(read_ports, "read_ports"),
            "write_ports": check_positive(write_ports, "write_ports"),
            "byte_write": p_byte_write,
            "init": _check_init(init, p_depth, required=False),
            "output_register": check_bool(output_register, "output_register"),
            "addr_bits": max(1, ceil_log2(p_depth)),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        addr_bits = self._params["addr_bits"]
        write_ports = self._params["write_ports"]
        read_ports = self._params["read_ports"]
        lanes = width // 8
        sig = {"clk": Signal(bool(0)), "resetn": Signal(bool(0))}
        for p in range(write_ports):
            sig[f"we{p}"] = Signal(bool(0))
            sig[f"waddr{p}"] = Signal(intbv(0, min=0, max=1 << addr_bits))
            sig[f"wdata{p}"] = Signal(intbv(0)[width:])
            if self._params["byte_write"]:
                sig[f"wstrb{p}"] = Signal(intbv(0)[lanes:])
        for p in range(read_ports):
            sig[f"raddr{p}"] = Signal(intbv(0, min=0, max=1 << addr_bits))
            sig[f"rdata{p}"] = Signal(intbv(0)[width:])
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the RAM onto *ports* and return its instances."""
        params = self._params
        width = params["width"]
        depth = params["depth"]
        nwrite = params["write_ports"]
        nread = params["read_ports"]
        byte_write = params["byte_write"]
        full = mask(width)

        proclist = []
        mem = [
            Signal(intbv(self._params["init"][i] & full)[width:]) for i in range(depth)
        ]

        we = tuple(ports[f"we{p}"] for p in range(nwrite))
        waddr = tuple(ports[f"waddr{p}"] for p in range(nwrite))
        wdata = tuple(ports[f"wdata{p}"] for p in range(nwrite))
        raddr = tuple(ports[f"raddr{p}"] for p in range(nread))
        rdata = tuple(ports[f"rdata{p}"] for p in range(nread))

        if byte_write:
            lanes = width // 8
            lane_masks = [((1 << 8) - 1) << (8 * b) for b in range(lanes)]
            wvalue_list = []
            for p in range(nwrite):
                old = Signal(intbv(0)[width:])
                proclist.append(rf_old(mem, waddr[p], old, depth))
                cur = old
                for b in range(lanes):
                    nxt = Signal(intbv(0)[width:])
                    proclist.append(
                        rf_lane(
                            ports[f"wstrb{p}"],
                            b,
                            cur,
                            wdata[p],
                            lane_masks[b],
                            full,
                            nxt,
                        )
                    )
                    cur = nxt
                wvalue_list.append(cur)
            wvalue = tuple(wvalue_list)
        else:
            wvalue = wdata

        for p in range(nwrite):
            proclist.append(
                rf_wr_port(
                    mem,
                    ports.clk,
                    ports.resetn,
                    ports[f"we{p}"],
                    ports[f"waddr{p}"],
                    wvalue[p],
                    depth,
                    False,
                    0,
                    False,
                )
            )

        stages = params["read_latency"] + (1 if params["output_register"] else 0)
        write_first = params["write_mode"] == WRITE_FIRST
        no_change = params["write_mode"] == NO_CHANGE
        for p in range(nread):
            if stages == 0:
                if write_first:
                    base = Signal(intbv(0)[width:])
                    proclist.append(rf_base(mem, raddr[p], base, depth, False, 0))
                    proclist.append(
                        rf_bypass(base, rdata[p], raddr[p], we, waddr, wvalue, nwrite)
                    )
                else:
                    proclist.append(rf_base(mem, raddr[p], rdata[p], depth, False, 0))
                continue
            base = Signal(intbv(0)[width:])
            proclist.append(rf_base(mem, raddr[p], base, depth, False, 0))
            if write_first:
                nxt = Signal(intbv(0)[width:])
                proclist.append(
                    rf_bypass(base, nxt, raddr[p], we, waddr, wvalue, nwrite)
                )
                src = nxt
            else:
                src = base
            blocked = None
            if no_change:
                blocked = Signal(bool(0))
                proclist.append(rf_blocked(raddr[p], we, waddr, blocked, nwrite))
            if stages == 1:
                proclist.append(
                    rf_capture(
                        src, rdata[p], ports.clk, ports.resetn, True, no_change, blocked
                    )
                )
            else:
                stage = Signal(intbv(0)[width:])
                proclist.append(
                    rf_capture(
                        src, stage, ports.clk, ports.resetn, True, no_change, blocked
                    )
                )
                proclist.append(
                    rf_capture(
                        stage, rdata[p], ports.clk, ports.resetn, True, False, None
                    )
                )

        return proclist


class SyncRom(ComponentBase):
    """Read-only synchronous memory (``IC-FR-140..144``).

    Args:
        width, depth: geometry.
        init: ROM contents (required, length ``depth``).
        read_latency: ``0`` combinational read, ``1`` registered read.
        read_ports: number of read ports.
        output_register: extra output register stage.
    """

    def __init__(
        self,
        width: int,
        depth: int,
        init,
        read_latency: int = 1,
        read_ports: int = 1,
        output_register: bool = False,
    ) -> None:
        p_width = check_positive(width, "width")
        p_depth = check_positive(depth, "depth")
        self._params = {
            "width": p_width,
            "depth": p_depth,
            "init": _check_init(init, p_depth, required=True),
            "read_latency": check_registered(read_latency, "read_latency"),
            "read_ports": check_positive(read_ports, "read_ports"),
            "output_register": check_bool(output_register, "output_register"),
            "addr_bits": max(1, ceil_log2(p_depth)),
        }

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        addr_bits = self._params["addr_bits"]
        sig = {"clk": Signal(bool(0)), "resetn": Signal(bool(0))}
        for p in range(self._params["read_ports"]):
            sig[f"raddr{p}"] = Signal(intbv(0, min=0, max=1 << addr_bits))
            sig[f"rdata{p}"] = Signal(intbv(0)[width:])
        return SignalView(**sig)

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the ROM onto *ports* and return its instances."""
        params = self._params
        width = params["width"]
        depth = params["depth"]
        full = mask(width)
        nread = params["read_ports"]
        stages = params["read_latency"] + (1 if params["output_register"] else 0)

        proclist = []
        mem = [
            Signal(intbv(self._params["init"][i] & full)[width:]) for i in range(depth)
        ]

        for p in range(nread):
            raddr = ports[f"raddr{p}"]
            rdata = ports[f"rdata{p}"]
            if stages == 0:
                proclist.append(rf_base(mem, raddr, rdata, depth, False, 0))
                continue
            base = Signal(intbv(0)[width:])
            proclist.append(rf_base(mem, raddr, base, depth, False, 0))
            if stages == 1:
                proclist.append(
                    rf_capture(
                        base,
                        rdata,
                        ports.clk,
                        ports.resetn,
                        True,
                        False,
                        None,
                    )
                )
            else:
                stage = Signal(intbv(0)[width:])
                proclist.append(
                    rf_capture(
                        base,
                        stage,
                        ports.clk,
                        ports.resetn,
                        True,
                        False,
                        None,
                    )
                )
                proclist.append(
                    rf_capture(
                        stage,
                        rdata,
                        ports.clk,
                        ports.resetn,
                        True,
                        False,
                        None,
                    )
                )

        return proclist
