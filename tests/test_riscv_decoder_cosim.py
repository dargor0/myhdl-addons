"""Verilog cosimulation smoke test for ``InstructionDecoder`` (Option A)."""

from myhdl import StopSimulation, block, delay, instance
from test_riscv_decoder import _ALL_INSTRS

from myhdl_addons.riscv import InstructionDecoder


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


def _cosim_device(hdl_cosim, name):
    def _make(comp, ports):
        return hdl_cosim(comp.hdl(ports), ports, name)

    return _make


@block
def _bench(make_device, instrs, results):
    comp = InstructionDecoder()
    ports = comp.ports()
    dut = make_device(comp, ports)

    @instance
    def stim():
        ports.instr.next = 0
        yield delay(1)
        for instr in instrs:
            ports.instr.next = instr
            yield delay(1)
            results.append(
                tuple(int(ports[name]) for name in ports.names if name != "instr")
            )
        raise StopSimulation

    return dut, stim


def _run(make_device):
    results = []
    _bench(make_device, _ALL_INSTRS, results).run_sim()
    return results


def test_decoder_cosim_matches_python(hdl_cosim):
    python = _run(_python_device)
    cosim = _run(_cosim_device(hdl_cosim, "decoder_cosim"))
    assert cosim == python
