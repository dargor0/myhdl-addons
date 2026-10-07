"""Verilog cosimulation smoke test for the C front-end plug-in (Option A).

The converted registry-built ``RvcDecompressor`` is driven over the same
vectors as the RVC tests and must agree with the golden :func:`decompress`
reference.  (A Python-device comparison is not possible here: MyHDL requires a
sub-block to be instantiated directly in a ``@block`` body, whereas the
registry builds it through ``front_end``.)
"""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv
from test_riscv_rvc_cosim import _VECTORS

from myhdl_addons.common.views import SignalView
from myhdl_addons.riscv import decompress, default_registry


def _context():
    return SignalView(
        instr_i=Signal(intbv(0)[16:]),
        instr_o=Signal(intbv(0)[32:]),
        illegal=Signal(bool(0)),
    )


def _cosim_device(hdl_cosim, name):
    def _make(registry, context):
        return hdl_cosim(registry.build(context)[0], context, name)

    return _make


@block
def _bench(make_device, vectors, results):
    registry = default_registry()
    registry.select(["c"])
    context = _context()
    dut = make_device(registry, context)

    @instance
    def stim():
        context.instr_i.next = 0xFFFF  # prime the combinational front-end
        yield delay(1)
        for instr in vectors:
            context.instr_i.next = instr
            yield delay(1)
            results.append((int(context.instr_o), int(context.illegal)))
        raise StopSimulation

    return dut, stim


def test_c_extension_cosim_matches_reference(hdl_cosim):
    results = []
    _bench(_cosim_device(hdl_cosim, "c_ext_cosim"), _VECTORS, results).run_sim()
    assert results == [decompress(instr) for instr in _VECTORS]
