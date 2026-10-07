"""Verilog cosimulation smoke test for ``ImmGen`` (Option A)."""

from myhdl import StopSimulation, block, delay, instance
from test_riscv_immgen import _VECTORS

from myhdl_addons.riscv import ImmGen


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name)

    return _make


@block
def _bench(make_device, vectors, results):
    comp = ImmGen()
    ports = comp.ports()
    imm_map = comp.get_imm_intmap()
    dut = make_device(comp, ports)

    @instance
    def stim():
        ports.instr.next = 0
        ports.imm_sel.next = 0
        yield delay(1)
        for word, kind in vectors:
            ports.instr.next = word
            ports.imm_sel.next = imm_map[kind]
            yield delay(1)
            results.append(int(ports.imm))
        raise StopSimulation

    return dut, stim


def _run(make_device):
    results = []
    _bench(make_device, _VECTORS, results).run_sim()
    return results


def test_immgen_cosim_matches_python(hdl_cosim):
    python = _run(_python_device)
    cosim = _run(_cosim_device(hdl_cosim, "immgen_cosim"))
    assert cosim == python
