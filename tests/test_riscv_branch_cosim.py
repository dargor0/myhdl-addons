"""Verilog cosimulation smoke tests for ``BranchUnit``/``jalr_target`` (Option A)."""

from myhdl import Signal, StopSimulation, block, delay, instance, intbv
from test_riscv_branch import _VECTORS, _WIDTH

from myhdl_addons.common.views import SignalView
from myhdl_addons.riscv import BranchUnit, jalr_target


def _ports():
    return SignalView(
        a=Signal(intbv(0)[_WIDTH:]),
        b=Signal(intbv(0)[_WIDTH:]),
        op=Signal(intbv(0)[3:]),
        take=Signal(bool(0)),
    )


@block
def _dut(ports):
    return BranchUnit(width=_WIDTH).hdl(ports)


@block
def _bench(make_dut, ports, vectors, results):
    op_map = BranchUnit(width=_WIDTH).get_op_intmap()
    dut = make_dut(ports)

    @instance
    def stim():
        # prime with a value differing from the first vector so the converted
        # combinational block fires at time 0
        ports.a.next = 0xFF
        ports.b.next = 0
        ports.op.next = 0
        yield delay(1)
        for a, b, name in vectors:
            ports.a.next = a
            ports.b.next = b
            ports.op.next = op_map[name]
            yield delay(1)
            results.append(int(ports.take))
        raise StopSimulation

    return dut, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, _VECTORS, results).run_sim()
    return results


def test_branch_unit_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "branch_cosim")

    assert _run(cosim) == _run(_dut)


def _jalr_ports():
    return SignalView(
        addr_i=Signal(intbv(0)[32:]),
        jalr=Signal(bool(0)),
        addr_o=Signal(intbv(0)[32:]),
    )


@block
def _jalr_dut(ports):
    return jalr_target(ports.addr_i, ports.jalr, ports.addr_o)


@block
def _jalr_bench(make_dut, ports, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.addr_i.next = 0x12345679
        ports.jalr.next = 1
        yield delay(1)
        results.append(int(ports.addr_o))
        ports.jalr.next = 0
        yield delay(1)
        results.append(int(ports.addr_o))
        raise StopSimulation

    return dut, stim


def _run_jalr(make_dut):
    ports = _jalr_ports()
    results = []
    _jalr_bench(make_dut, ports, results).run_sim()
    return results


def test_jalr_target_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_jalr_dut(ports), ports, "jalr_target_cosim")

    assert _run_jalr(cosim) == _run_jalr(_jalr_dut)
