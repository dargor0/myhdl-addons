"""Verilog cosimulation smoke test for ``RvcDecompressor`` (Option A).

The same bench (stimulus + capture) drives either the Python block or the
converted Verilog RTL through :class:`myhdl.Cosimulation`; both must produce
identical ``(instr_o, illegal)`` results.  Exhaustive equivalence against the
golden :func:`decompress` reference is proven by ``test_riscv_rvc.py``; this
test only proves the *converted RTL* agrees with the Python block on a
representative sweep (every ``op``/``funct3`` pair plus directed edge cases).
"""

from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.riscv import RvcDecompressor

# Directed cases: the golden-function vectors from ``test_riscv_rvc.py`` plus
# a reserved encoding and the uncompressed (``op == 0b11``) quadrant.
_DIRECTED = (
    0x0001,  # c.nop
    0x0085,  # c.addi x1, 1
    0x50FD,  # c.li x1, -1
    0x8082,  # c.jr x1
    0x9002,  # c.ebreak
    0xA001,  # c.j offset 0
    0xB001,  # c.j with sign bit set
    0x2001,  # c.jal offset 0
    0x3001,  # c.jal with sign bit set
    0x9C01,  # reserved c.sub family (inst[12] == 1)
    0x0000,  # c.addi4spn with nzuimm == 0
    0x0003,  # op == 0b11 (not compressed)
    0xFFFF,  # op == 0b11 (not compressed)
)


def _sweep():
    """Every ``(op, funct3)`` pair with a spread of operand/immediate bits."""
    vectors = set(_DIRECTED)
    longs = (0x0000, 0x00C0, 0x0800, 0x0F80, 0x1000, 0x1555, 0x1AAA, 0x1FFC)
    for op in (0, 1, 2, 3):
        for f3 in range(8):
            for low in longs:
                vectors.add((f3 << 13) | (low & 0x1FFC) | op)
    return sorted(vectors)


_VECTORS = _sweep()


@block
def _python_device(rvc, ports):
    return rvc.hdl(ports)


def _cosim_device(hdl_cosim, name):
    def _make(rvc, ports):
        return hdl_cosim(rvc.hdl(ports), ports, name)

    return _make


@block
def _rvc_bench(make_device, vectors, results):
    rvc = RvcDecompressor()
    ports = rvc.ports()
    dut = make_device(rvc, ports)

    @instance
    def stim():
        # prime the combinational device so its converted always block fires
        # even when the first vector equals the power-on value (0x0000)
        ports.instr_i.next = 0xFFFF
        yield delay(1)
        for instr in vectors:
            ports.instr_i.next = instr
            yield delay(1)
            results.append((int(ports.instr_o), int(ports.illegal)))
        raise StopSimulation

    return dut, stim


def _run(make_device):
    results = []
    _rvc_bench(make_device, _VECTORS, results).run_sim()
    return results


def test_rvc_decompressor_cosim_matches_python(hdl_cosim):
    python = _run(_python_device)
    cosim = _run(_cosim_device(hdl_cosim, "rvc_cosim"))
    assert cosim == python
