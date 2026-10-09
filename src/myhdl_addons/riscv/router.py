"""Address-region map + memory router (``RC-FR-104/105/107/109/077``).

The :class:`MemoryRouter` is the single memory fabric of the core: **fetch**
and **data** are two clients of the same router (``RC-FR-102``), each speaking
the uniform router protocol (Q31 / ``RC-FR-104``)::

    req_valid/addr[/we/wdata/wstrb]  ->  resp_valid/rdata/error

with **one outstanding access per client**.  The data client carries the store
fields; the fetch client is read-only and omits them.  Every access is
dispatched by the
**address-region map** (``RC-FR-107``) — an arbitrary set of power-of-two,
base-aligned, non-overlapping regions ``(base, size, perms, access, target)``
decoded with a mask (``addr & (size-1)``).  ``perms`` selects the fetch/data
clients allowed, ``access`` is ``RO``/``RW`` and ``target`` is ``internal`` for
this step (external buses are added next).

Internal regions instantiate the generic :class:`~myhdl_addons.components.SyncRam`
(``D`` and ``RW``) or :class:`~myhdl_addons.components.SyncRom` otherwise, with
``read_ports`` = 2 for ``perms = ID`` (a **dual-port** memory so fetch and data
never contend) and 1 otherwise (``RC-FR-106``/Q34).  Stores place their bytes
and raise the byte strobes from ``size``/``addr``.

Access faults (``RC-FR-077``) are reported through ``resp_error``: an access to
an unmapped address, a fetch from a region without ``I``, a load/store to a
region without ``D`` or a store to an ``RO`` region.  The router only issues a
read for an allowed region; the detection is purely combinational + registered
alongside the accepted request.
"""

import itertools

from myhdl import Signal, always, always_comb, block, intbv

from ..bus_common.muxing import or_chain, select_chain
from ..common.config import (
    ComponentBase,
    check_choice,
    check_power_of_two,
    check_positive,
)
from ..common.errors import HdlConfigError
from ..common.reset import make_reset
from ..common.views import SignalView
from ..components import AddressDecoder, SyncRam, SyncRom

__all__ = ["MemoryRouter"]

_AVAIL_PERMS = ("I", "D", "ID")
_AVAIL_ACCESS = ("RO", "RW")

#: A never-matching window used to give a client that has no regions of some
#: kind a decoder (and hence a constantly-low ``valid``), avoiding an
#: unconditional signal that could not be driven from an ``always_comb``.
_SENTINEL = 0xFFFF_FFFC


def _normalize_regions(regions) -> tuple[dict, ...]:
    """Validate and canonicalise the address-region map.

    ``target`` is ``"internal"`` (an on-chip memory) or ``"bus:<name>"`` (an
    external bus).  Only **one** external bus is supported at this step
    (``RC-FR-101``; multiple buses are added at M5 / ``WP-34``).
    """
    entries = tuple(regions)
    if not entries:
        raise HdlConfigError("at least one region is required")
    limit = 1 << 32
    buses: set[str] = set()
    result = []
    for region in entries:
        if not isinstance(region, dict):
            raise HdlConfigError(f"region must be a dict, got {region!r}")
        name = region.get("name", "?")
        target = str(region.get("target", "internal"))
        if target == "internal":
            bus = None
        elif target.startswith("bus:") and target[4:]:
            bus = target[4:]
            buses.add(bus)
        else:
            raise HdlConfigError(
                f"region {name!r}: target must be 'internal' or 'bus:<name>', "
                f"got {target!r}"
            )
        base = int(region["base"])
        size = check_power_of_two(int(region["size"]), f"region {name!r} size")
        if size < 4:
            raise HdlConfigError(f"region {name!r} size must be at least one word")
        if base < 0 or base + size > limit:
            raise HdlConfigError(f"region {name!r} exceeds the 32-bit address space")
        if base % size != 0:
            raise HdlConfigError(f"region {name!r} base must be aligned to its size")
        perms = check_choice(
            str(region.get("perms", "ID")).upper(),
            _AVAIL_PERMS,
            f"region {name!r} perms",
        )
        access = check_choice(
            str(region.get("access", "RW")).upper(),
            _AVAIL_ACCESS,
            f"region {name!r} access",
        )
        result.append(
            {
                "name": name,
                "base": base,
                "size": size,
                "perms": perms,
                "access": access,
                "bus": bus,
            }
        )
    if len(buses) > 1:
        raise HdlConfigError(
            f"multiple external buses {sorted(buses)} are scheduled for M5 / WP-34; "
            f"only one is supported"
        )
    ordered = sorted(result, key=lambda r: r["base"])
    for lower, upper in itertools.pairwise(ordered):
        if lower["base"] + lower["size"] > upper["base"]:
            raise HdlConfigError(
                f"regions {lower['name']!r} and {upper['name']!r} overlap"
            )
    return tuple(result)


@block
def select_reg(clk, reset, active, accept, sel, out):
    """Register a one-hot region select alongside an accepted request."""

    @always(clk.posedge)
    def p():
        if reset == active:
            out.next = 0
        elif accept:
            out.next = sel

    return p


@block
def router_resp(
    clk,
    reset,
    active,
    req_valid,
    sels,
    read_data,
    req_error,
    req_accept,
    resp_valid,
    resp_rdata,
    resp_error,
    adr_width,
):
    """One router client: accept a request, register its target, mux the reply.

    The accepted request's one-hot region select is registered, and the memory
    read data is muxed back one cycle later with the registered select.  A
    request that matched no allowed region (or violated a permission) is
    registered as an error (``req_error``).  ``req_accept``, when not ``None``,
    exposes the one-cycle accept pulse (used to gate stores).
    """
    n = len(sels)
    pending = Signal(bool(0))
    fault = Signal(bool(0))
    accept = Signal(bool(0))

    @always_comb
    def calc_accept():
        if req_valid and (not pending):
            accept.next = 1
        else:
            accept.next = 0

    proclist = [calc_accept]
    registered = []
    for i in range(n):
        sig = Signal(bool(0))
        registered.append(sig)
        proclist.append(select_reg(clk, reset, active, accept, sels[i], sig))

    if n:
        proclist.append(
            select_chain(registered, read_data, resp_rdata, adr_width, False)
        )
        if req_accept is None:

            @always_comb
            def drive_resp():
                resp_valid.next = pending
                resp_error.next = fault

        else:

            @always_comb
            def drive_resp():
                req_accept.next = accept
                resp_valid.next = pending
                resp_error.next = fault

    elif req_accept is None:

        @always_comb
        def drive_resp():
            resp_valid.next = pending
            resp_error.next = fault
            resp_rdata.next = 0

    else:

        @always_comb
        def drive_resp():
            req_accept.next = accept
            resp_valid.next = pending
            resp_error.next = fault
            resp_rdata.next = 0

    proclist.append(drive_resp)

    @always(clk.posedge)
    def state():
        if reset == active:
            pending.next = 0
            fault.next = 0
        elif accept:
            pending.next = 1
            fault.next = req_error
        elif pending:
            pending.next = 0

    proclist.append(state)
    return proclist


@block
def router_client(
    clk,
    reset,
    active,
    req_valid,
    req_addr,
    req_we,
    req_wdata,
    req_wstrb,
    int_sels,
    int_read_data,
    ext_route,
    req_error,
    bus_req_valid,
    bus_req_addr,
    bus_req_we,
    bus_req_wdata,
    bus_req_wstrb,
    bus_resp_valid,
    bus_resp_rdata,
    bus_resp_error,
    resp_valid,
    resp_rdata,
    resp_error,
    req_accept,
    adr_width,
):
    """One client with an internal memory path and an external-bus path.

    An accepted request is routed to the internal memory (response one cycle
    later) or, when it matched an external region (``ext_route``), to the bus
    client (response when ``bus_resp_valid`` arrives).  An unmatched or
    permission-violating request is registered as an error and answered on the
    internal cadence.  ``req_we`` (and the store fields) are ``None`` for the
    read-only fetch client.
    """
    store = req_we is not None
    n = len(int_sels)
    pending = Signal(bool(0))
    ext = Signal(bool(0))
    fault = Signal(bool(0))
    accept = Signal(bool(0))
    adr_l = Signal(intbv(0)[adr_width:])
    we_l = Signal(bool(0))
    wdata_l = Signal(intbv(0)[adr_width:])
    wstrb_l = Signal(intbv(0)[adr_width // 8 :])
    int_rdata = Signal(intbv(0)[adr_width:])

    if n == 0:

        @always_comb
        def calc_accept():
            int_rdata.next = 0
            if req_valid and (not pending):
                accept.next = 1
            else:
                accept.next = 0

    else:

        @always_comb
        def calc_accept():
            if req_valid and (not pending):
                accept.next = 1
            else:
                accept.next = 0

    proclist = [calc_accept]
    registered = []
    for i in range(n):
        sig = Signal(bool(0))
        registered.append(sig)
        proclist.append(select_reg(clk, reset, active, accept, int_sels[i], sig))
    if n:
        proclist.append(
            select_chain(registered, int_read_data, int_rdata, adr_width, False)
        )

    if store:

        @always_comb
        def combine():
            bus_req_valid.next = pending and ext
            bus_req_addr.next = adr_l
            bus_req_we.next = we_l
            bus_req_wdata.next = wdata_l
            bus_req_wstrb.next = wstrb_l
            if pending and (not ext):
                resp_valid.next = 1
            elif bus_resp_valid:
                resp_valid.next = 1
            else:
                resp_valid.next = 0
            if ext:
                resp_rdata.next = bus_resp_rdata
                resp_error.next = bus_resp_error
            else:
                resp_rdata.next = int_rdata
                resp_error.next = fault

    else:

        @always_comb
        def combine():
            bus_req_valid.next = pending and ext
            bus_req_addr.next = adr_l
            if pending and (not ext):
                resp_valid.next = 1
            elif bus_resp_valid:
                resp_valid.next = 1
            else:
                resp_valid.next = 0
            if ext:
                resp_rdata.next = bus_resp_rdata
                resp_error.next = bus_resp_error
            else:
                resp_rdata.next = int_rdata
                resp_error.next = fault

    proclist.append(combine)

    if req_accept is not None:

        @always_comb
        def drive_accept():
            req_accept.next = accept

        proclist.append(drive_accept)

    if store:

        @always(clk.posedge)
        def state():
            if reset == active:
                pending.next = 0
                ext.next = 0
                fault.next = 0
            else:
                if accept:
                    pending.next = 1
                    ext.next = ext_route
                    fault.next = req_error
                    if ext_route:
                        adr_l.next = req_addr
                        we_l.next = req_we
                        wdata_l.next = req_wdata
                        wstrb_l.next = req_wstrb
                elif pending and ((not ext) or bus_resp_valid):
                    pending.next = 0

    else:

        @always(clk.posedge)
        def state():
            if reset == active:
                pending.next = 0
                ext.next = 0
                fault.next = 0
            else:
                if accept:
                    pending.next = 1
                    ext.next = ext_route
                    fault.next = req_error
                    if ext_route:
                        adr_l.next = req_addr
                elif pending and ((not ext) or bus_resp_valid):
                    pending.next = 0

    proclist.append(state)
    return proclist


@block
def mem_read_addr(adr, raddr, size):
    """Word index within a region from the masked byte offset."""

    @always_comb
    def p():
        raddr.next = (int(adr) & (size - 1)) >> 2

    return p


@block
def mem_store(
    accept, sel, req_we, addr, wdata, wstrb, we, waddr, wdata_o, wstrb_o, sizemask
):
    """Drive the selected region's write port (the client placed the bytes)."""

    @always_comb
    def p():
        if accept and req_we and sel:
            we.next = 1
            waddr.next = (int(addr) & sizemask) >> 2
            wdata_o.next = wdata
            wstrb_o.next = wstrb
        else:
            we.next = 0
            wstrb_o.next = 0

    return p


class MemoryRouter(ComponentBase):
    """Address-region memory router with fetch/data clients (``RC-FR-105``).

    Args:
        regions: iterable of region dicts ``{base, size, perms, access,
            target, name}`` (as returned by ``CoreConfig.regions``);
            ``target`` is ``"internal"`` or ``"bus:<name>"`` (one external bus).
        contents: optional ``{region_name: sequence_of_words}`` internal-memory
            images (one 32-bit word each); read-only regions default to zeros.
        width: data/address width (32 for RV32).
        reset_signal: reuse a specific ``ResetSignal``, or ``None``.

    Ports: ``clk``/``reset`` and the two Q31 clients ``f_*`` (fetch,
    read-only: ``req_valid``/``req_addr``) and ``d_*`` (data:
    ``req_valid``/``req_addr``/``req_we``/``req_wdata``/``req_wstrb``), each with
    ``resp_valid``/``resp_rdata``/``resp_error`` out.  When the map has an
    external region it also exposes the bus-master client ports ``f_bus_*``/
    ``d_bus_*`` (the assembler ties them to a ``BusMaster``).
    """

    def __init__(
        self, regions, contents=None, width: int = 32, reset_signal=None
    ) -> None:
        p_regions = _normalize_regions(regions)
        p_contents = {name: tuple(image) for name, image in (contents or {}).items()}
        names = {region["name"]: region for region in p_regions}
        for key, image in p_contents.items():
            if key not in names:
                raise HdlConfigError(f"contents for unknown region {key!r}")
            if names[key]["bus"] is not None:
                raise HdlConfigError(
                    f"contents for external region {key!r} is not supported"
                )
            depth = names[key]["size"] // 4
            if len(image) != depth:
                raise HdlConfigError(
                    f"contents for region {key!r} length {len(image)} != depth {depth}"
                )
        self._contents = p_contents
        self._params = {
            "width": check_positive(width, "width"),
            "regions": p_regions,
            "reset_signal": make_reset(reset_signal),
        }

    @property
    def has_external(self) -> bool:
        """Whether the map routes any region to an external bus."""
        return any(region["bus"] is not None for region in self._params["regions"])

    def ports(self) -> SignalView:
        """Allocate and return the component interface."""
        width = self._params["width"]
        sig = {
            "clk": Signal(bool(0)),
            "reset": self._params["reset_signal"],
            "f_req_valid": Signal(bool(0)),
            "f_req_addr": Signal(intbv(0)[width:]),
            "f_resp_valid": Signal(bool(0)),
            "f_resp_rdata": Signal(intbv(0)[width:]),
            "f_resp_error": Signal(bool(0)),
            "d_req_valid": Signal(bool(0)),
            "d_req_addr": Signal(intbv(0)[width:]),
            "d_req_we": Signal(bool(0)),
            "d_req_wdata": Signal(intbv(0)[width:]),
            "d_req_wstrb": Signal(intbv(0)[width // 8 :]),
            "d_resp_valid": Signal(bool(0)),
            "d_resp_rdata": Signal(intbv(0)[width:]),
            "d_resp_error": Signal(bool(0)),
        }
        if self.has_external:
            # Q31 client ports of the external bus master (driven to a
            # BusMaster by the assembler); the fetch bus client is read-only.
            sig["f_bus_req_valid"] = Signal(bool(0))
            sig["f_bus_req_addr"] = Signal(intbv(0)[width:])
            sig["f_bus_resp_valid"] = Signal(bool(0))
            sig["f_bus_resp_rdata"] = Signal(intbv(0)[width:])
            sig["f_bus_resp_error"] = Signal(bool(0))
            sig["d_bus_req_valid"] = Signal(bool(0))
            sig["d_bus_req_addr"] = Signal(intbv(0)[width:])
            sig["d_bus_req_we"] = Signal(bool(0))
            sig["d_bus_req_wdata"] = Signal(intbv(0)[width:])
            sig["d_bus_req_wstrb"] = Signal(intbv(0)[width // 8 :])
            sig["d_bus_resp_valid"] = Signal(bool(0))
            sig["d_bus_resp_rdata"] = Signal(intbv(0)[width:])
            sig["d_bus_resp_error"] = Signal(bool(0))
        return SignalView(**sig)

    def _build_memory(self, region):
        width = self._params["width"]
        depth = region["size"] // 4
        perms = region["perms"]
        ram = ("D" in perms) and (region["access"] == "RW")
        nread = 2 if perms == "ID" else 1
        image = self._contents.get(region["name"])
        keyword = {"read_ports": nread, "reset_signal": self._params["reset_signal"]}
        if ram:
            memory = SyncRam(
                width=width,
                depth=depth,
                byte_write=width // 8,
                write_ports=1,
                init=image,
                **keyword,
            )
        else:
            if image is None:
                image = tuple(0 for _ in range(depth))
            memory = SyncRom(width=width, depth=depth, init=image, **keyword)
        return memory, ram

    @block
    def hdl(self, ports: SignalView):
        """Elaborate the router onto *ports* and return its instances."""
        width = self._params["width"]
        active = int(self._params["reset_signal"].active)
        regions = self._params["regions"]
        internal = [region for region in regions if region["bus"] is None]
        external = [region for region in regions if region["bus"] is not None]
        has_external = bool(external)

        proclist = []
        mems = []
        for region in internal:
            memory, ram = self._build_memory(region)
            mports = memory.ports()
            mports.clk = ports.clk
            proclist.append(memory.hdl(mports))
            mems.append({"region": region, "ports": mports, "ram": ram})

        # ---- fetch client ----
        f_mems = [m for m in mems if "I" in m["region"]["perms"]]
        f_int_list = [m["region"] for m in f_mems]
        f_int_decoder = AddressDecoder(
            adr_width=width,
            windows=[(r["base"], r["size"]) for r in f_int_list] or [(_SENTINEL, 4)],
            valid=True,
        )
        f_int_dports = f_int_decoder.ports()
        f_int_dports.adr = ports.f_req_addr
        proclist.append(f_int_decoder.hdl(f_int_dports))
        f_int_sels = [f_int_dports[f"sel{i}"] for i in range(len(f_int_list))]
        f_int_valid = f_int_dports.valid
        f_read = []
        for mem in f_mems:
            f_read.append(mem["ports"]["rdata0"])
            proclist.append(
                mem_read_addr(
                    ports.f_req_addr,
                    mem["ports"]["raddr0"],
                    mem["region"]["size"],
                )
            )

        f_error = Signal(bool(0))
        if has_external:
            f_ext_list = [r for r in external if "I" in r["perms"]]
            f_ext_decoder = AddressDecoder(
                adr_width=width,
                windows=[(r["base"], r["size"]) for r in f_ext_list]
                or [(_SENTINEL, 4)],
                valid=True,
            )
            f_ext_dports = f_ext_decoder.ports()
            f_ext_dports.adr = ports.f_req_addr
            proclist.append(f_ext_decoder.hdl(f_ext_dports))
            f_ext_valid = f_ext_dports.valid

            @always_comb
            def calc_f_error():
                if ports.f_req_valid and (not (f_int_valid or f_ext_valid)):
                    f_error.next = 1
                else:
                    f_error.next = 0

        else:

            @always_comb
            def calc_f_error():
                if ports.f_req_valid and (not f_int_valid):
                    f_error.next = 1
                else:
                    f_error.next = 0

        proclist.append(calc_f_error)

        # ---- data client ----
        d_mems = [m for m in mems if "D" in m["region"]["perms"]]
        d_int_list = [m["region"] for m in d_mems]
        d_int_decoder = AddressDecoder(
            adr_width=width,
            windows=[(r["base"], r["size"]) for r in d_int_list] or [(_SENTINEL, 4)],
            valid=True,
        )
        d_int_dports = d_int_decoder.ports()
        d_int_dports.adr = ports.d_req_addr
        proclist.append(d_int_decoder.hdl(d_int_dports))
        d_int_sels = [d_int_dports[f"sel{i}"] for i in range(len(d_int_list))]
        d_int_valid = d_int_dports.valid
        d_read = []
        d_int_ro_sels = []
        for i, mem in enumerate(d_mems):
            port = 1 if mem["region"]["perms"] == "ID" else 0
            d_read.append(mem["ports"][f"rdata{port}"])
            proclist.append(
                mem_read_addr(
                    ports.d_req_addr,
                    mem["ports"][f"raddr{port}"],
                    mem["region"]["size"],
                )
            )
            if mem["region"]["access"] == "RO":
                d_int_ro_sels.append(d_int_sels[i])

        d_error = Signal(bool(0))
        d_ro_any = Signal(bool(0))
        d_ext_route = None
        if has_external:
            d_ext = [r for r in external if "D" in r["perms"]]
            d_ext_decoder = AddressDecoder(
                adr_width=width,
                windows=[(r["base"], r["size"]) for r in d_ext] or [(_SENTINEL, 4)],
                valid=True,
            )
            d_ext_dports = d_ext_decoder.ports()
            d_ext_dports.adr = ports.d_req_addr
            proclist.append(d_ext_decoder.hdl(d_ext_dports))
            d_ext_sels = [d_ext_dports[f"sel{i}"] for i in range(len(d_ext))]
            d_ext_valid = d_ext_dports.valid
            d_ext_ro_sels = [
                d_ext_sels[i] for i, r in enumerate(d_ext) if r["access"] == "RO"
            ]
            d_ro_sels = d_int_ro_sels + d_ext_ro_sels
            if d_ro_sels:
                proclist.append(or_chain(d_ro_sels, d_ro_any))

                @always_comb
                def calc_d_error():
                    if ports.d_req_valid and (
                        (not (d_int_valid or d_ext_valid))
                        or (ports.d_req_we and d_ro_any)
                    ):
                        d_error.next = 1
                    else:
                        d_error.next = 0

            else:

                @always_comb
                def calc_d_error():
                    if ports.d_req_valid and (not (d_int_valid or d_ext_valid)):
                        d_error.next = 1
                    else:
                        d_error.next = 0

            d_ext_ro_any = Signal(bool(0))
            d_ext_route = Signal(bool(0))
            if d_ext_ro_sels:
                proclist.append(or_chain(d_ext_ro_sels, d_ext_ro_any))

                @always_comb
                def calc_d_ext_route():
                    if ports.d_req_we and d_ext_ro_any:
                        d_ext_route.next = 0
                    else:
                        d_ext_route.next = d_ext_valid

            else:

                @always_comb
                def calc_d_ext_route():
                    d_ext_route.next = d_ext_valid

            proclist.append(calc_d_ext_route)

        else:
            d_ro_sels = d_int_ro_sels
            if d_ro_sels:
                proclist.append(or_chain(d_ro_sels, d_ro_any))

                @always_comb
                def calc_d_error():
                    if ports.d_req_valid and (
                        (not d_int_valid) or (ports.d_req_we and d_ro_any)
                    ):
                        d_error.next = 1
                    else:
                        d_error.next = 0

            else:

                @always_comb
                def calc_d_error():
                    if ports.d_req_valid and (not d_int_valid):
                        d_error.next = 1
                    else:
                        d_error.next = 0

        proclist.append(calc_d_error)

        d_accept = Signal(bool(0)) if any(m["ram"] for m in d_mems) else None
        if has_external:
            proclist.append(
                router_client(
                    ports.clk,
                    ports.reset,
                    active,
                    ports.f_req_valid,
                    ports.f_req_addr,
                    None,
                    None,
                    None,
                    f_int_sels,
                    f_read,
                    f_ext_valid,
                    f_error,
                    ports.f_bus_req_valid,
                    ports.f_bus_req_addr,
                    None,
                    None,
                    None,
                    ports.f_bus_resp_valid,
                    ports.f_bus_resp_rdata,
                    ports.f_bus_resp_error,
                    ports.f_resp_valid,
                    ports.f_resp_rdata,
                    ports.f_resp_error,
                    None,
                    width,
                )
            )
            proclist.append(
                router_client(
                    ports.clk,
                    ports.reset,
                    active,
                    ports.d_req_valid,
                    ports.d_req_addr,
                    ports.d_req_we,
                    ports.d_req_wdata,
                    ports.d_req_wstrb,
                    d_int_sels,
                    d_read,
                    d_ext_route,
                    d_error,
                    ports.d_bus_req_valid,
                    ports.d_bus_req_addr,
                    ports.d_bus_req_we,
                    ports.d_bus_req_wdata,
                    ports.d_bus_req_wstrb,
                    ports.d_bus_resp_valid,
                    ports.d_bus_resp_rdata,
                    ports.d_bus_resp_error,
                    ports.d_resp_valid,
                    ports.d_resp_rdata,
                    ports.d_resp_error,
                    d_accept,
                    width,
                )
            )
        else:
            proclist.append(
                router_resp(
                    ports.clk,
                    ports.reset,
                    active,
                    ports.f_req_valid,
                    f_int_sels,
                    f_read,
                    f_error,
                    None,
                    ports.f_resp_valid,
                    ports.f_resp_rdata,
                    ports.f_resp_error,
                    width,
                )
            )
            proclist.append(
                router_resp(
                    ports.clk,
                    ports.reset,
                    active,
                    ports.d_req_valid,
                    d_int_sels,
                    d_read,
                    d_error,
                    d_accept,
                    ports.d_resp_valid,
                    ports.d_resp_rdata,
                    ports.d_resp_error,
                    width,
                )
            )

        for i, mem in enumerate(d_mems):
            if mem["ram"]:
                proclist.append(
                    mem_store(
                        d_accept,
                        d_int_sels[i],
                        ports.d_req_we,
                        ports.d_req_addr,
                        ports.d_req_wdata,
                        ports.d_req_wstrb,
                        mem["ports"]["we0"],
                        mem["ports"]["waddr0"],
                        mem["ports"]["wdata0"],
                        mem["ports"]["wstrb0"],
                        mem["region"]["size"] - 1,
                    )
                )

        return proclist
