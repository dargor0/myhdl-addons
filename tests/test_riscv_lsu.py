"""``LoadStoreUnit`` sizes, extension, strobes and misalign (``RC-FR-070..072``)."""

from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.riscv import LoadStoreUnit

_MASK = 0xFFFF_FFFF


def _sext(value, bits):
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _load_ref(rdata, addr, size, zero_extend):
    if size == 2:
        return rdata & _MASK
    if size == 1:
        value = (rdata >> (8 * (addr & 2))) & 0xFFFF
        bits = 16
    else:
        value = (rdata >> (8 * (addr & 3))) & 0xFF
        bits = 8
    if zero_extend:
        return value
    return _sext(value, bits) & _MASK


def _store_ref(wdata, addr, size):
    if size == 2:
        return wdata & _MASK, 0b1111
    if size == 1:
        off = addr & 2
        return ((wdata & 0xFFFF) << (8 * off)) & _MASK, 0b11 << off
    off = addr & 3
    return ((wdata & 0xFF) << (8 * off)) & _MASK, 1 << off


def _misalign_ref(addr, size):
    if size == 2:
        return int((addr & 3) != 0)
    if size == 1:
        return addr & 1
    return 0


_ADDRS = (
    0x00000000,
    0x00000001,
    0x00000002,
    0x00000003,
    0x00000004,
    0x00000005,
    0x00000006,
    0x00000007,
    0x00000008,
    0x0000000F,
    0xDEADBEE4,
    0x0000FFFE,
    0xFFFFFFFD,
)
_WDATA = (0x00000000, 0x000000FF, 0x12345678, 0xFFFFFFFF, 0x80000001)
_RDATA = (0x00000000, 0xFFFFFFFF, 0x89ABCDEF, 0x0000FF00, 0x12345678, 0x80)

_VECTORS = [
    (addr, wdata, rdata, size, zero_extend)
    for addr in _ADDRS
    for wdata in _WDATA
    for rdata in _RDATA
    for size in (0, 1, 2)
    for zero_extend in (0, 1)
]


@block
def _lsu_tb(results, vectors):
    comp = LoadStoreUnit()
    ports = comp.ports()
    dut = comp.hdl(ports)

    @instance
    def stim():
        for addr, wdata, rdata, size, zero_extend in vectors:
            ports.addr.next = addr
            ports.wdata.next = wdata
            ports.rdata.next = rdata
            ports.size.next = size
            ports.zero_extend.next = zero_extend
            yield delay(1)
            results.append(
                (
                    int(ports.load_data),
                    int(ports.store_data),
                    int(ports.wstrb),
                    int(ports.misaligned),
                )
            )
        raise StopSimulation

    return dut, stim


def _run(vectors):
    results = []
    _lsu_tb(results, vectors).run_sim()
    return results


def test_lsu_matches_reference():
    for (addr, wdata, rdata, size, zero_extend), got in zip(
        _VECTORS, _run(_VECTORS)
    ):
        load, store, strobe, misaligned = got
        assert load == _load_ref(rdata, addr, size, zero_extend), (
            hex(addr),
            size,
            zero_extend,
        )
        assert (store, strobe) == _store_ref(wdata, addr, size), (hex(addr), size)
        assert misaligned == _misalign_ref(addr, size), (hex(addr), size)


def test_lsu_directed_loads():
    rdata = 0x89ABCDEF
    # byte lanes 0..3
    assert _run([(0, 0, rdata, 0, 0)])[0][0] == 0xFFFFFFEF  # LB lane 0 (neg)
    assert _run([(1, 0, rdata, 0, 0)])[0][0] == 0xFFFFFFCD  # LB lane 1
    assert _run([(2, 0, rdata, 0, 1)])[0][0] == 0x000000AB  # LBU lane 2
    assert _run([(3, 0, rdata, 0, 0)])[0][0] == 0xFFFFFF89  # LB lane 3
    # halfwords (little-endian)
    assert _run([(0, 0, rdata, 1, 0)])[0][0] == 0xFFFFCDEF  # LH low
    assert _run([(0, 0, rdata, 1, 1)])[0][0] == 0x0000CDEF  # LHU low
    assert _run([(2, 0, rdata, 1, 0)])[0][0] == 0xFFFF89AB  # LH high
    # word
    assert _run([(0, 0, rdata, 2, 0)])[0][0] == rdata


def test_lsu_directed_stores():
    assert _run([(0, 0x11223344, 0, 0, 0)])[0][1:] == (0x00000044, 0b0001, 0)
    assert _run([(1, 0x11223344, 0, 0, 0)])[0][1] == 0x00004400
    assert _run([(1, 0x11223344, 0, 0, 0)])[0][2] == 0b0010
    assert _run([(2, 0x11223344, 0, 0, 0)])[0][1] == 0x00440000
    assert _run([(3, 0x11223344, 0, 0, 0)])[0][1] == 0x44000000
    assert _run([(2, 0x11223344, 0, 1, 0)])[0][1:] == (0x33440000, 0b1100, 0)
    assert _run([(0, 0x11223344, 0, 2, 0)])[0][1:] == (0x11223344, 0b1111, 0)


def test_lsu_misalignment():
    assert _misalign_ref(0x2, 1) == 0
    assert _run([(0x2, 0, 0, 1, 0)])[0][3] == 0
    assert _run([(0x1, 0, 0, 1, 0)])[0][3] == 1  # misaligned LH
    assert _run([(0x1, 0, 0, 2, 0)])[0][3] == 1  # misaligned LW
    assert _run([(0x3, 0, 0, 0, 0)])[0][3] == 0  # LB is never misaligned


def test_lsu_unused_size_is_byte():
    # `size` is 2 bits but the decoder only emits 0/1/2; 3 falls through to byte
    vector = [(1, 0x11223344, 0x89ABCDEF, 3, 0)]
    assert _run(vector) == _run([(1, 0x11223344, 0x89ABCDEF, 0, 0)])
