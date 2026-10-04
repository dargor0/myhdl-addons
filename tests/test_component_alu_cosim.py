"""Verilog cosimulation smoke test for the ``Alu`` (Option A).

The same bench (stimulus + checks) drives either the Python block or the
converted Verilog RTL through :class:`myhdl.Cosimulation`; both must produce
identical results.  This is the proof-of-concept for the component cosim
harness (the converted RTL is bound to the component's own ``SignalView``).
"""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Alu


@block
def _python_device(alu, ports):
    return alu.hdl(ports)


def _cosim_device(hdl_cosim, name):
    def _make(alu, ports):
        return hdl_cosim(alu.hdl(ports), ports, name)

    return _make


@block
def _alu_comb_bench(make_device, vectors, results):
    alu = Alu(width=8)  # all ops and flags
    ports = alu.ports()
    opmap = alu.get_op_intmap()
    dut = make_device(alu, ports)

    @instance
    def stim():
        for opname, a, b in vectors:
            ports.a.next = a
            ports.b.next = b
            if isinstance(opname, str):
                ports.op.next = opmap[opname]
            else:
                ports.op.next = opname
            yield delay(1)
            results.append(
                (
                    int(ports.y),
                    int(ports.zero),
                    int(ports.lt),
                    int(ports.ltu),
                    int(ports.carry),
                )
            )
        raise StopSimulation

    return dut, stim


_COMB_VECTORS = [
    ("ADD", 0x00, 0x00),
    ("ADD", 0x7F, 0x01),
    ("ADD", 0xFF, 0x01),
    ("SUB", 0x01, 0x02),
    ("AND", 0xF0, 0x0F),
    ("OR", 0xF0, 0x0F),
    ("XOR", 0xFF, 0xAA),
    ("SLT", 0x80, 0x01),
    ("SLTU", 0x80, 0x01),
    ("PASS_A", 0x12, 0x34),
    ("PASS_B", 0x12, 0x34),
    ("NOP", 0x12, 0x34),
    (15, 0x12, 0x34),  # out-of-range op code -> 0
]


def _run_comb(make_device):
    results = []
    _alu_comb_bench(make_device, _COMB_VECTORS, results).run_sim()
    return results


def test_alu_comb_cosim_matches_python(hdl_cosim):
    python = _run_comb(_python_device)
    cosim = _run_comb(_cosim_device(hdl_cosim, "alu_cosim_comb"))
    assert cosim == python


@block
def _alu_reg_bench(make_device, results):
    alu = Alu(width=8, ops=["ADD"], flags=["zero"], registered=1, en=True)
    ports = alu.ports()
    dut = make_device(alu, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.reset.next = 1
        ports.en.next = 1
        ports.a.next = 10
        ports.b.next = 5
        ports.op.next = alu.get_op_intmap()["ADD"]
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.en.next = 0
        ports.a.next = 20
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return clkgen, dut, stim


def _run_reg(make_device):
    results = []
    _alu_reg_bench(make_device, results).run_sim()
    return results


def test_alu_registered_cosim_matches_python(hdl_cosim):
    python = _run_reg(_python_device)
    cosim = _run_reg(_cosim_device(hdl_cosim, "alu_cosim_reg"))
    assert cosim == python == [0, 15, 15]
