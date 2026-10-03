"""Multi-port register file (``IC-FR-020..029``).

A parameterised, bus-agnostic register bank with configurable read/write
port counts, read latency, same-address write mode and an optional
constant-register feature (``zero_reg_fix_value``).

Convertibility shapes the implementation: the storage is a list-of-signals
free variable (MyHDL memory inference), written by one clocked process and read
by per-port processes; the byte-strobe merge is a chain of small lane muxes.
"""

from myhdl import Signal, always, always_comb, block, intbv

from ..common.config import (
    ComponentBase,
    ceil_log2,
    check_bool,
    check_choice,
    check_non_negative,
    check_positive,
    check_registered,
    mask,
)
from ..common.errors import HdlConfigError
from ..common.views import SignalView

__all__ = [
    "NO_CHANGE",
    "READ_FIRST",
    "WRITE_FIRST",
    "WRITE_MODES",
    "RegisterFile",
]

READ_FIRST = "read_first"
WRITE_FIRST = "write_first"
NO_CHANGE = "no_change"
WRITE_MODES = (READ_FIRST, WRITE_FIRST, NO_CHANGE)


@block
def rf_base(mem, raddr, base, depth, zero_reg, zero_fix):
    """Combinational memory read with zero-register and range handling."""

    if zero_reg:

        @always_comb
        def p():
            if raddr == 0:
                base.next = zero_fix
            elif raddr < depth:
                base.next = mem[raddr]
            else:
                base.next = 0

    else:

        @always_comb
        def p():
            if raddr < depth:
                base.next = mem[raddr]
            else:
                base.next = 0

    return p


@block
def rf_bypass(base, dst, raddr, we, waddr, wvalue, nwrite):
    """Write-first bypass: shadow ``base`` with a matching write value."""

    @always_comb
    def p():
        dst.next = base
        for j in range(nwrite):
            if we[j] and waddr[j] == raddr:
                dst.next = wvalue[j]

    return p


@block
def rf_blocked(raddr, we, waddr, blocked, nwrite):
    """Flag whether any write port targets the read address this cycle."""

    @always_comb
    def p():
        hit = 0
        for j in range(nwrite):
            if we[j] and waddr[j] == raddr:
                hit = 1
        blocked.next = hit != 0

    return p


@block
def rf_capture(d, q, clk, resetn, reset_enable, hold, blocked):
    """Registered read capture: ``reset > hold-on-same-address-write > d``."""

    if reset_enable:
        if hold:

            @always(clk.posedge)
            def p():
                if not resetn:
                    q.next = 0
                else:
                    if not blocked:
                        q.next = d

        else:

            @always(clk.posedge)
            def p():
                if not resetn:
                    q.next = 0
                else:
                    q.next = d

    else:
        if hold:

            @always(clk.posedge)
            def p():
                if not blocked:
                    q.next = d

        else:

            @always(clk.posedge)
            def p():
                q.next = d

    return p


@block
def rf_wr_port(
    mem, clk, resetn, we, waddr, wvalue, depth, reset_enable, reset_value, zero_reg
):
    """Synchronous writes for one port, with optional reset and zero-register.

    One process per write port keeps every write port signal individually
    referenced (so MyHDL marks the ports as read) and matches a true
    multi-write-port memory.
    """

    if reset_enable:
        if zero_reg:

            @always(clk.posedge)
            def p():
                if not resetn:
                    for i in range(depth):
                        mem[i].next = reset_value
                else:
                    if we and waddr < depth and waddr != 0:
                        mem[waddr].next = wvalue

        else:

            @always(clk.posedge)
            def p():
                if not resetn:
                    for i in range(depth):
                        mem[i].next = reset_value
                else:
                    if we and waddr < depth:
                        mem[waddr].next = wvalue

    else:
        if zero_reg:

            @always(clk.posedge)
            def p():
                if we and waddr < depth and waddr != 0:
                    mem[waddr].next = wvalue

        else:

            @always(clk.posedge)
            def p():
                if we and waddr < depth:
                    mem[waddr].next = wvalue

    return p


@block
def rf_old(mem, waddr, old, depth):
    """Read the current memory word (for byte-strobe merging)."""

    @always_comb
    def p():
        if waddr < depth:
            old.next = mem[waddr]
        else:
            old.next = 0

    return p


@block
def rf_lane(wstrb, b, src, wdata, lane_mask, full, dst):
    """One byte-lane merge stage gated by ``wstrb[b]``."""

    keep = full ^ lane_mask

    @always_comb
    def p():
        if wstrb[b]:
            dst.next = (src & keep) | (wdata & lane_mask)
        else:
            dst.next = src

    return p


class RegisterFile(ComponentBase):
    """Multi-port register file (``IC-FR-020..029``).

    Args:
        width, depth: word width and number of entries.
        read_ports, write_ports: port counts.
        read_latency: ``0`` asynchronous read, ``1`` registered read.
        write_mode: same-address behaviour (``read_first``/``write_first``/
            ``no_change``); fully honoured by registered reads.
        zero_reg_fix_value: read-only constant for index ``0`` (``None`` off).
        reset_enable, reset_value: reset behaviour.
        init: optional per-entry initialisation image.
        byte_write: per-write-port byte strobes.
    """

    def __init__(
        self,
        width: int = 32,
        depth: int = 32,
        read_ports: int = 2,
        write_ports: int = 1,
        read_latency: int = 0,
        write_mode: str = READ_FIRST,
        zero_reg_fix_value: int | None = None,
        reset_enable: bool = True,
        reset_value: int = 0,
        init=None,
        byte_write: bool = False,
    ) -> None:
        p_width = check_positive(width, "width")
        p_depth = check_positive(depth, "depth")
        p_byte_write = check_bool(byte_write, "byte_write")
        if p_byte_write and p_width % 8 != 0:
            raise HdlConfigError(
                f"byte_write requires width multiple of 8, got {p_width}"
            )
        p_zero_reg = (
            None
            if zero_reg_fix_value is None
            else check_non_negative(zero_reg_fix_value, "zero_reg_fix_value")
        )
        p_reset_value = check_non_negative(reset_value, "reset_value")
        if init is None:
            p_init = None
        else:
            values = tuple(init)
            if len(values) != p_depth:
                raise HdlConfigError(
                    f"init image length {len(values)} != depth {p_depth}"
                )
            for value in values:
                check_non_negative(value, "init entry")
            p_init = values
        self._params = {
            "width": p_width,
            "depth": p_depth,
            "read_ports": check_positive(read_ports, "read_ports"),
            "write_ports": check_positive(write_ports, "write_ports"),
            "read_latency": check_registered(read_latency, "read_latency"),
            "write_mode": check_choice(write_mode, WRITE_MODES, "write_mode"),
            "zero_reg_fix_value": p_zero_reg,
            "reset_enable": check_bool(reset_enable, "reset_enable"),
            "reset_value": p_reset_value,
            "init": p_init,
            "byte_write": p_byte_write,
            "addr_bits": max(1, ceil_log2(p_depth)),
        }

    def _initial(self, index: int) -> int:
        init = self._params["init"]
        value = init[index] if init is not None else self._params["reset_value"]
        return value & mask(self._params["width"])

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
        """Elaborate the register file onto *ports* and return its instances."""
        params = self._params
        width = params["width"]
        depth = params["depth"]
        nwrite = params["write_ports"]
        nread = params["read_ports"]
        byte_write = params["byte_write"]
        zero_reg = params["zero_reg_fix_value"] is not None
        zero_fix = params["zero_reg_fix_value"] or 0
        reset_enable = params["reset_enable"]
        reset_value = params["reset_value"] & mask(width)
        write_mode = params["write_mode"]
        read_latency = params["read_latency"]
        full = mask(width)

        proclist = []

        mem = [Signal(intbv(self._initial(i))[width:]) for i in range(depth)]

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
                    reset_enable,
                    reset_value,
                    zero_reg,
                )
            )

        write_first = write_mode == WRITE_FIRST
        no_change = write_mode == NO_CHANGE
        for p in range(nread):
            if read_latency == 0:
                if write_first:
                    base = Signal(intbv(0)[width:])
                    proclist.append(
                        rf_base(mem, raddr[p], base, depth, zero_reg, zero_fix)
                    )
                    proclist.append(
                        rf_bypass(base, rdata[p], raddr[p], we, waddr, wvalue, nwrite)
                    )
                else:
                    proclist.append(
                        rf_base(mem, raddr[p], rdata[p], depth, zero_reg, zero_fix)
                    )
            else:
                base = Signal(intbv(0)[width:])
                proclist.append(rf_base(mem, raddr[p], base, depth, zero_reg, zero_fix))
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
                proclist.append(
                    rf_capture(
                        src,
                        rdata[p],
                        ports.clk,
                        ports.resetn,
                        reset_enable,
                        no_change,
                        blocked,
                    )
                )

        return proclist
