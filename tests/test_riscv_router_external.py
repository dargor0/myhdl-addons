"""``MemoryRouter`` external-region routing through a ``BusMaster``.

The router routes ``target = "bus:<name>"`` regions to its ``f_bus_*``/
``d_bus_*`` Q31 client ports; this bench ties those to a ``BusMaster`` whose
Wishbone master drives a behavioural slave.
"""

from myhdl import StopSimulation, always, always_comb, block, delay, instance
from test_riscv_busmaster import _Mem, _slave
from test_riscv_router import _align

from myhdl_addons.riscv import BusMaster, MemoryRouter

_RAM = (0xAAAA0000, 0, 0, 0)


def _regions(perms="ID", access="RW"):
    return [
        {"name": "ram", "base": 0x00, "size": 0x10, "perms": "ID", "access": "RW"},
        {
            "name": "per",
            "base": 0x100,
            "size": 0x10,
            "perms": perms,
            "access": access,
            "target": "bus:wb",
        },
    ]


def _contents():
    return {"ram": _RAM}


def _slave_mem():
    return _Mem({0x100: 0x11111111, 0x104: 0x22222222})


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


@block
def _glue(rports, bports):
    @always_comb
    def f_req():
        bports.c0_req_valid.next = rports.f_bus_req_valid
        bports.c0_req_addr.next = rports.f_bus_req_addr

    @always_comb
    def f_resp():
        rports.f_bus_resp_valid.next = bports.c0_resp_valid
        rports.f_bus_resp_rdata.next = bports.c0_resp_rdata
        rports.f_bus_resp_error.next = bports.c0_resp_error

    @always_comb
    def d_req():
        bports.c1_req_valid.next = rports.d_bus_req_valid
        bports.c1_req_addr.next = rports.d_bus_req_addr
        bports.c1_req_we.next = rports.d_bus_req_we
        bports.c1_req_wdata.next = rports.d_bus_req_wdata
        bports.c1_req_wstrb.next = rports.d_bus_req_wstrb

    @always_comb
    def d_resp():
        rports.d_bus_resp_valid.next = bports.c1_resp_valid
        rports.d_bus_resp_rdata.next = bports.c1_resp_rdata
        rports.d_bus_resp_error.next = bports.c1_resp_error

    return f_req, f_resp, d_req, d_resp


@block
def _ext_tb(make_router, make_bus, results, ops, slave_mem, perms, access):
    router = MemoryRouter(_regions(perms, access), contents=_contents())
    busmaster = BusMaster()
    rports = router.ports()
    bports = busmaster.ports()
    rdut = make_router(router, rports)
    bdut = make_bus(busmaster, bports)

    # The router and the bus master run in the same clock/reset domain; their
    # signals are separate objects, so both are driven together.
    @always(delay(5))
    def clkgen():
        rports.clk.next = not rports.clk
        bports.clk.next = not bports.clk

    @instance
    def stim():
        rports.reset.next = 0
        bports.reset.next = 0
        yield rports.clk.posedge
        rports.reset.next = 1
        bports.reset.next = 1
        yield rports.clk.posedge
        for op in ops:
            client = op["client"]
            getattr(rports, f"{client}_req_addr").next = op["addr"]
            if client == "d":
                we = op.get("we", 0)
                rports.d_req_we.next = we
                if we:
                    aligned, strobes = _align(
                        op["addr"], op.get("size", 0), op.get("wdata", 0)
                    )
                    rports.d_req_wdata.next = aligned
                    rports.d_req_wstrb.next = strobes
                else:
                    rports.d_req_wdata.next = 0
                    rports.d_req_wstrb.next = 0b1111
            getattr(rports, f"{client}_req_valid").next = 1
            yield delay(1)
            guard = 0
            while not getattr(rports, f"{client}_resp_valid"):
                yield rports.clk.posedge
                yield delay(1)
                guard += 1
                assert guard < 300
            results.append(
                (
                    int(getattr(rports, f"{client}_resp_rdata")),
                    int(getattr(rports, f"{client}_resp_error")),
                )
            )
            getattr(rports, f"{client}_req_valid").next = 0
            yield rports.clk.posedge
            yield delay(1)
        raise StopSimulation

    return clkgen, rdut, bdut, _glue(rports, bports), _slave(bports, slave_mem), stim


def _run(make_router, make_bus, ops, perms="ID", access="RW", slave_mem=None):
    results = []
    mem = slave_mem if slave_mem is not None else _slave_mem()
    _ext_tb(make_router, make_bus, results, ops, mem, perms, access).run_sim()
    return results


_OPS = [
    {"client": "f", "addr": 0x00},  # internal RAM
    {"client": "f", "addr": 0x100},  # external read
    {"client": "d", "addr": 0x104},  # external read
    {"client": "d", "addr": 0x108, "we": 1, "wdata": 0xDEADBEEF, "size": 2},
    {"client": "f", "addr": 0x108},  # read back the store
    {"client": "d", "addr": 0x00, "we": 1, "wdata": 0x12345678, "size": 2},
    {"client": "f", "addr": 0x00},  # internal read-after-write
    {"client": "f", "addr": 0x200},  # unmapped -> fault
]


def test_router_external_regions():
    got = _run(_python_device, _python_device, _OPS)
    assert got[0] == (0xAAAA0000, 0)
    assert got[1] == (0x11111111, 0)
    assert got[2] == (0x22222222, 0)
    assert got[4] == (0xDEADBEEF, 0)
    assert got[6] == (0x12345678, 0)
    assert got[7] == (0, 1)
    assert all(error == 0 for _, error in got[:7])


def test_router_external_ro_store_faults():
    ops = [
        {"client": "d", "addr": 0x100, "we": 1, "wdata": 0x1, "size": 2},
        {"client": "d", "addr": 0x100},  # read still allowed
    ]
    got = _run(_python_device, _python_device, ops, access="RO")
    assert got == [(0, 1), (0x11111111, 0)]


def test_router_external_perms_i_only():
    ops = [
        {"client": "f", "addr": 0x100},  # fetch allowed
        {"client": "d", "addr": 0x100},  # data to I-only external -> fault
    ]
    got = _run(_python_device, _python_device, ops, perms="I", access="RO")
    assert got == [(0x11111111, 0), (0, 1)]


def test_router_external_perms_d_only():
    ops = [
        {"client": "d", "addr": 0x100},  # data allowed
        {"client": "f", "addr": 0x100},  # fetch to D-only external -> fault
    ]
    got = _run(_python_device, _python_device, ops, perms="D", access="RW")
    assert got == [(0x11111111, 0), (0, 1)]
