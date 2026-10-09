"""``MemoryRouter`` region decode, reads/writes and access faults.

The router has two Q31 clients (fetch and data); this bench drives them
sequentially and records ``(rdata, error)`` per access.  Internal regions use
known contents.
"""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.common.errors import HdlConfigError
from myhdl_addons.riscv import MemoryRouter

_ROM = (0x11111111, 0x22222222, 0x33333333, 0x44444444)
_RAM = (0x00000000, 0x00000000, 0x00000000, 0x00000000)
_IO = (0x55000000, 0x00000000, 0x00000000, 0x00000000)


def _regions():
    return [
        {"name": "rom", "base": 0x00, "size": 0x10, "perms": "ID", "access": "RO"},
        {"name": "ram", "base": 0x10, "size": 0x10, "perms": "ID", "access": "RW"},
        {"name": "io", "base": 0x20, "size": 0x10, "perms": "D", "access": "RW"},
    ]


def _contents():
    return {"rom": _ROM, "ram": _RAM, "io": _IO}


def _router():
    return MemoryRouter(_regions(), contents=_contents())


def _align(addr, size, value):
    """Little-endian store lane placement + byte strobes (as the LSU does)."""
    if size == 2:
        return value & 0xFFFFFFFF, 0b1111
    if size == 1:
        if addr & 2:
            return (value & 0xFFFF) << 16, 0b1100
        return value & 0xFFFF, 0b0011
    lane = addr & 0x3
    return (value & 0xFF) << (8 * lane), 1 << lane


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


@block
def _router_tb(make_device, results, comp, ops):
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        yield ports.clk.posedge
        for op in ops:
            client = op["client"]
            getattr(ports, f"{client}_req_addr").next = op["addr"]
            if client == "d":
                we = op.get("we", 0)
                ports.d_req_we.next = we
                if we:
                    aligned, strobes = _align(
                        op["addr"], op.get("size", 0), op.get("wdata", 0)
                    )
                    ports.d_req_wdata.next = aligned
                    ports.d_req_wstrb.next = strobes
                else:
                    ports.d_req_wdata.next = 0
                    ports.d_req_wstrb.next = 0b1111
            getattr(ports, f"{client}_req_valid").next = 1
            yield ports.clk.posedge
            yield delay(1)
            while not getattr(ports, f"{client}_resp_valid"):
                yield ports.clk.posedge
                yield delay(1)
            results.append(
                (
                    int(getattr(ports, f"{client}_resp_rdata")),
                    int(getattr(ports, f"{client}_resp_error")),
                )
            )
            getattr(ports, f"{client}_req_valid").next = 0
            yield ports.clk.posedge
            yield delay(1)
        raise StopSimulation

    return clkgen, dut, stim


def _run(make_device, ops, comp=None):
    results = []
    comp = comp or _router()
    _router_tb(make_device, results, comp, ops).run_sim()
    return results


def test_router_reads_known_words():
    ops = [
        {"client": "f", "addr": 0x00, "size": 2},
        {"client": "f", "addr": 0x04, "size": 2},
        {"client": "d", "addr": 0x00, "size": 2},
        {"client": "d", "addr": 0x08, "size": 2},
        {"client": "f", "addr": 0x10, "size": 2},
        {"client": "d", "addr": 0x20, "size": 2},
    ]
    got = _run(_python_device, ops)
    assert got == [
        (0x11111111, 0),
        (0x22222222, 0),
        (0x11111111, 0),
        (0x33333333, 0),
        (0x00000000, 0),
        (0x55000000, 0),
    ]


def test_router_store_then_load():
    ops = [
        {"client": "d", "addr": 0x10, "we": 1, "wdata": 0x11223344, "size": 2},
        {"client": "d", "addr": 0x10, "size": 2},
        {"client": "d", "addr": 0x11, "we": 1, "wdata": 0x000000AA, "size": 0},
        {"client": "d", "addr": 0x10, "size": 2},
        {"client": "d", "addr": 0x12, "we": 1, "wdata": 0x0000BEEF, "size": 1},
        {"client": "d", "addr": 0x10, "size": 2},
    ]
    got = _run(_python_device, ops)
    assert got[1] == (0x11223344, 0)
    assert got[3] == (0x1122AA44, 0)
    assert got[5] == (0xBEEFAA44, 0)
    assert all(error == 0 for _, error in got)


def test_router_byte_store_each_lane():
    ops = []
    for lane in range(4):
        ops.append(
            {
                "client": "d",
                "addr": 0x10 + lane,
                "we": 1,
                "wdata": 0x80 + lane,
                "size": 0,
            }
        )
    ops.append({"client": "d", "addr": 0x10, "size": 2})
    got = _run(_python_device, ops)
    # bytes 0x80,0x81,0x82,0x83 little-endian
    assert got[-1] == (0x83828180, 0)


def test_router_halfword_store_lanes():
    ops = [
        {"client": "d", "addr": 0x10, "we": 1, "wdata": 0x0000BEEF, "size": 1},
        {"client": "d", "addr": 0x12, "we": 1, "wdata": 0x0000CAFE, "size": 1},
        {"client": "d", "addr": 0x10, "size": 2},
    ]
    got = _run(_python_device, ops)
    assert got[-1] == (0xCAFEBEEF, 0)


def test_router_faults():
    ops = [
        {"client": "f", "addr": 0x20, "size": 2},  # io has no I
        {"client": "f", "addr": 0x40, "size": 2},  # unmapped
        {"client": "d", "addr": 0x40, "size": 2},  # unmapped
        {"client": "d", "addr": 0x00, "we": 1, "wdata": 1, "size": 2},  # rom RO
        {"client": "d", "addr": 0x00, "size": 2},  # rom load is fine
    ]
    got = _run(_python_device, ops)
    assert [error for _, error in got] == [1, 1, 1, 1, 0]
    assert got[4][0] == 0x11111111


@block
def _concurrent_tb(make_device, out, comp, faddr, daddr):
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        yield ports.clk.posedge
        ports.f_req_addr.next = faddr
        ports.f_req_valid.next = 1
        ports.d_req_addr.next = daddr
        ports.d_req_wstrb.next = 0b1111
        ports.d_req_valid.next = 1
        yield ports.clk.posedge
        ports.f_req_valid.next = 0
        ports.d_req_valid.next = 0
        yield delay(1)
        out.append(
            (int(ports.f_resp_valid), int(ports.f_resp_rdata), int(ports.f_resp_error))
        )
        out.append(
            (int(ports.d_resp_valid), int(ports.d_resp_rdata), int(ports.d_resp_error))
        )
        raise StopSimulation

    return clkgen, dut, stim


def test_router_dual_port_no_contention():
    # fetch and data hit the same ID RAM region in the same cycle
    out = []
    _concurrent_tb(_python_device, out, _router(), 0x10, 0x14).run_sim()
    assert out == [(1, 0x00000000, 0), (1, 0x00000000, 0)]
    assert out[0][0] == out[1][0] == 1


def test_router_rom_only_faults_data():
    comp = MemoryRouter(
        [{"name": "rom", "base": 0, "size": 0x10, "perms": "I", "access": "RO"}],
        contents={"rom": _ROM},
    )
    got = _run(
        _python_device,
        [
            {"client": "f", "addr": 0x04, "size": 2},
            {"client": "d", "addr": 0x04, "size": 2},
        ],
        comp,
    )
    assert got == [(0x22222222, 0), (0, 1)]


def test_router_data_only_faults_fetch():
    comp = MemoryRouter(
        [{"name": "ram", "base": 0, "size": 0x10, "perms": "D", "access": "RW"}],
        contents={"ram": _RAM},
    )
    got = _run(
        _python_device,
        [
            {"client": "d", "addr": 0x00, "size": 2},
            {"client": "f", "addr": 0x00, "size": 2},
        ],
        comp,
    )
    assert got == [(0, 0), (0, 1)]


def test_router_parameters_and_validation():
    comp = _router()
    assert comp.as_dict()["width"] == 32
    assert len(comp.as_dict()["regions"]) == 3
    assert "MemoryRouter" in repr(comp)

    with pytest.raises(HdlConfigError):
        MemoryRouter([])
    with pytest.raises(HdlConfigError):
        MemoryRouter([{"name": "x", "base": 0, "size": 0x10, "target": "bus:"}])
    with pytest.raises(HdlConfigError):
        MemoryRouter(
            [
                {
                    "name": "a",
                    "base": 0,
                    "size": 0x10,
                    "perms": "ID",
                    "target": "bus:p",
                },
                {
                    "name": "b",
                    "base": 0x10,
                    "size": 0x10,
                    "perms": "ID",
                    "target": "bus:q",
                },
            ]
        )
    with pytest.raises(HdlConfigError):
        MemoryRouter([{"name": "x", "base": 0, "size": 0x0C, "perms": "ID"}])
    with pytest.raises(HdlConfigError):
        MemoryRouter(
            [
                {"name": "a", "base": 0, "size": 0x20, "perms": "ID"},
                {"name": "b", "base": 0x10, "size": 0x10, "perms": "ID"},
            ]
        )
    with pytest.raises(HdlConfigError):
        MemoryRouter(
            [{"name": "a", "base": 0, "size": 0x10, "perms": "ID"}],
            contents={"a": (1, 2, 3)},
        )


def test_router_region_boundaries():
    # regions: rom 0x00..0x0F, ram 0x10..0x1F, io 0x20..0x2F
    ops = [
        {"client": "f", "addr": 0x0C, "size": 2},  # rom last word
        {"client": "f", "addr": 0x10, "size": 2},  # ram first word
        {"client": "f", "addr": 0x1C, "size": 2},  # ram last word
        {"client": "d", "addr": 0x20, "size": 2},  # io first word
        {"client": "d", "addr": 0x2C, "size": 2},  # io last word
        {"client": "f", "addr": 0x30, "size": 2},  # past io -> fault
        {"client": "d", "addr": 0x0F, "size": 0},  # rom last byte (word read)
    ]
    got = _run(_python_device, ops)
    assert got[0] == (0x44444444, 0)
    assert got[1] == (0x00000000, 0)
    assert got[2] == (0x00000000, 0)
    assert got[3] == (0x55000000, 0)
    assert got[4] == (0x00000000, 0)
    assert got[5] == (0, 1)
    assert got[6] == (0x44444444, 0)
