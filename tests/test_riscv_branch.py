"""``BranchUnit`` conditions and the ``jalr_target`` helper (``RC-FR-023``)."""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv

from myhdl_addons.riscv import AVAIL_BRANCH_OPS, BranchUnit, jalr_target

_WIDTH = 8


def _signed(value, width):
    sign = 1 << (width - 1)
    return (value ^ sign) - sign


def _reference(a, b, name, width):
    if name == "BEQ":
        return a == b
    if name == "BNE":
        return a != b
    if name == "BLT":
        return _signed(a, width) < _signed(b, width)
    if name == "BGE":
        return _signed(a, width) >= _signed(b, width)
    if name == "BLTU":
        return a < b
    if name == "BGEU":
        return a >= b
    raise ValueError(name)


_VALUES = (0x00, 0x01, 0x7F, 0x80, 0xFF)
_VECTORS = [
    (a, b, name) for a in _VALUES for b in _VALUES for name in AVAIL_BRANCH_OPS
]


@block
def _bu_tb(results, vectors, width):
    comp = BranchUnit(width=width)
    ports = comp.ports()
    dut = comp.hdl(ports)
    op_map = comp.get_op_intmap()

    @instance
    def stim():
        for a, b, name in vectors:
            ports.a.next = a
            ports.b.next = b
            ports.op.next = op_map[name]
            yield delay(1)
            results.append(int(ports.take))
        raise StopSimulation

    return dut, stim


def _run(vectors, width=_WIDTH):
    results = []
    _bu_tb(results, vectors, width).run_sim()
    return results


def test_branch_conditions():
    outputs = _run(_VECTORS)
    for (a, b, name), got in zip(_VECTORS, outputs):
        assert got == int(_reference(a, b, name, _WIDTH)), (a, b, name)


def test_branch_conditions_width32():
    vectors = [
        (0x80000000, 0x00000001, "BLT"),  # signed: most-negative < 1
        (0x80000000, 0x00000001, "BLTU"),  # unsigned: large > 1
        (0x80000000, 0x00000001, "BGE"),
        (0x80000000, 0x00000001, "BGEU"),
        (0x7FFFFFFF, 0xFFFFFFFF, "BLT"),
        (0xFFFFFFFF, 0x00000000, "BNE"),
        (0x12345678, 0x12345678, "BEQ"),
        (0x00000000, 0x00000000, "BGEU"),
    ]
    outputs = _run(vectors, 32)
    for (a, b, name), got in zip(vectors, outputs):
        assert got == int(_reference(a, b, name, 32)), (hex(a), hex(b), name)


@block
def _reserved_tb(results):
    comp = BranchUnit(width=32)
    ports = comp.ports()
    dut = comp.hdl(ports)

    @instance
    def stim():
        ports.a.next = 0xFFFFFFFF
        ports.b.next = 0x00000000
        for op in (0b010, 0b011):  # reserved branch funct3
            ports.op.next = op
            yield delay(1)
            results.append(int(ports.take))
        raise StopSimulation

    return dut, stim


def test_reserved_ops_take_zero():
    results = []
    _reserved_tb(results).run_sim()
    assert results == [0, 0]


@block
def _jalr_tb(results):
    addr_i = Signal(intbv(0)[32:])
    jalr = Signal(bool(0))
    addr_o = Signal(intbv(0)[32:])

    @instance
    def stim():
        addr_i.next = 0x12345679
        jalr.next = 1
        yield delay(1)
        results.append(int(addr_o))
        jalr.next = 0
        yield delay(1)
        results.append(int(addr_o))
        raise StopSimulation

    return jalr_target(addr_i, jalr, addr_o), stim


def test_jalr_target_clears_bit0():
    results = []
    _jalr_tb(results).run_sim()
    assert results == [0x12345678, 0x12345679]


def test_branch_exhaustive_width4():
    width = 4
    vectors = [
        (a, b, name)
        for a in range(1 << width)
        for b in range(1 << width)
        for name in AVAIL_BRANCH_OPS
    ]
    outputs = _run(vectors, width)
    for (a, b, name), got in zip(vectors, outputs):
        assert got == int(_reference(a, b, name, width)), (a, b, name)


@block
def _jalr_multi_tb(results, addrs):
    addr_i = Signal(intbv(0)[32:])
    jalr = Signal(bool(1))
    addr_o = Signal(intbv(0)[32:])

    @instance
    def stim():
        for addr in addrs:
            addr_i.next = addr
            yield delay(1)
            results.append(int(addr_o))
        raise StopSimulation

    return jalr_target(addr_i, jalr, addr_o), stim


def test_jalr_target_various():
    addrs = [0x00000000, 0x00000001, 0x00000002, 0x00000003,
             0xFFFFFFFD, 0xFFFFFFFF, 0x80000001]
    results = []
    _jalr_multi_tb(results, addrs).run_sim()
    assert results == [addr & 0xFFFFFFFE for addr in addrs]
