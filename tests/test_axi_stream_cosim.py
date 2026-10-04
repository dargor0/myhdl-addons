"""Verilog cosimulation smoke tests for the AXI4-Stream utilities (Option A).

Each utility is driven by a view-based bench against either the Python block or
the converted Verilog RTL; the observed samples must match.
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.axi import (
    axis_gate,
    axis_packet_counter,
    axis_periodic_gate,
    axis_register_slice,
    axis_width_down,
    axis_width_up,
)
from myhdl_addons.common.views import SignalView

_W8 = 8
_W16 = 16
_W32 = 32


# -- register slice --------------------------------------------------------


def _rs_ports():
    return SignalView(
        clk=Signal(bool(0)),
        resetn=Signal(bool(0)),
        din=Signal(intbv(0)[_W8:]),
        vin=Signal(bool(0)),
        lin=Signal(bool(0)),
        rin=Signal(bool(0)),
        dout=Signal(intbv(0)[_W8:]),
        vout=Signal(bool(0)),
        lout=Signal(bool(0)),
        rout=Signal(bool(0)),
    )


@block
def _rs_dut(p):
    return axis_register_slice(
        p.clk, p.resetn, p.din, p.vin, p.lin, p.rin, p.dout, p.vout, p.lout, p.rout
    )


@block
def _rs_bench(make_dut, p, results):
    dut = make_dut(p)

    @always(delay(5))
    def clkgen():
        p.clk.next = not p.clk

    @instance
    def stim():
        p.resetn.next = 0
        yield p.clk.posedge
        yield p.clk.posedge
        p.resetn.next = 1
        p.rout.next = 1
        p.din.next = 0x11
        p.vin.next = 1
        p.lin.next = 1
        yield p.clk.posedge
        yield delay(1)
        results.append((int(p.vout), int(p.dout), int(p.lout)))
        p.vin.next = 0
        yield p.clk.posedge
        yield delay(1)
        results.append((int(p.vout), int(p.dout)))
        raise StopSimulation

    return dut, clkgen, stim


def test_register_slice_cosim(hdl_cosim):
    def cosim(p):
        return hdl_cosim(_rs_dut(p), p, "axis_rs_cosim")

    assert _run(cosim, _rs_ports, _rs_bench) == _run(_rs_dut, _rs_ports, _rs_bench)


# -- gate ------------------------------------------------------------------


def _gate_ports():
    return SignalView(
        din=Signal(intbv(0)[_W8:]),
        vin=Signal(bool(0)),
        lin=Signal(bool(0)),
        rin=Signal(bool(0)),
        dout=Signal(intbv(0)[_W8:]),
        vout=Signal(bool(0)),
        lout=Signal(bool(0)),
        rout=Signal(bool(0)),
        enable=Signal(bool(0)),
    )


@block
def _gate_dut(p):
    return axis_gate(
        p.din, p.vin, p.lin, p.rin, p.dout, p.vout, p.lout, p.rout, p.enable
    )


@block
def _gate_bench(make_dut, p, results):
    dut = make_dut(p)

    @instance
    def stim():
        p.din.next = 0x7
        p.vin.next = 1
        p.lin.next = 1
        p.rout.next = 0
        p.enable.next = 0
        yield delay(1)
        results.append((int(p.vout), int(p.rin)))
        p.enable.next = 1
        yield delay(1)
        results.append((int(p.vout), int(p.dout), int(p.lout), int(p.rin)))
        raise StopSimulation

    return dut, stim


def test_gate_cosim(hdl_cosim):
    def cosim(p):
        return hdl_cosim(_gate_dut(p), p, "axis_gate_cosim")

    assert _run(cosim, _gate_ports, _gate_bench) == _run(
        _gate_dut, _gate_ports, _gate_bench
    )


# -- width down ------------------------------------------------------------


def _wd_ports():
    return SignalView(
        clk=Signal(bool(0)),
        resetn=Signal(bool(0)),
        din=Signal(intbv(0)[_W32:]),
        vin=Signal(bool(0)),
        lin=Signal(bool(0)),
        rin=Signal(bool(0)),
        dout=Signal(intbv(0)[_W16:]),
        vout=Signal(bool(0)),
        lout=Signal(bool(0)),
        rout=Signal(bool(0)),
    )


@block
def _wd_dut(p):
    return axis_width_down(
        p.clk, p.resetn, p.din, p.vin, p.lin, p.rin, p.dout, p.vout, p.lout, p.rout
    )


@block
def _wd_bench(make_dut, p, results):
    dut = make_dut(p)

    @always(delay(5))
    def clkgen():
        p.clk.next = not p.clk

    @instance
    def stim():
        p.resetn.next = 0
        yield p.clk.posedge
        yield p.clk.posedge
        p.resetn.next = 1
        p.rout.next = 1
        p.din.next = 0xAAAABBBB
        p.vin.next = 1
        p.lin.next = 1
        for _ in range(3):
            yield p.clk.posedge
            yield delay(1)
            results.append((int(p.vout), int(p.dout), int(p.lout)))
        raise StopSimulation

    return dut, clkgen, stim


def test_width_down_cosim(hdl_cosim):
    def cosim(p):
        return hdl_cosim(_wd_dut(p), p, "axis_wdown_cosim")

    assert _run(cosim, _wd_ports, _wd_bench) == _run(_wd_dut, _wd_ports, _wd_bench)


# -- width up --------------------------------------------------------------


def _wu_ports():
    return SignalView(
        clk=Signal(bool(0)),
        resetn=Signal(bool(0)),
        din=Signal(intbv(0)[_W16:]),
        vin=Signal(bool(0)),
        lin=Signal(bool(0)),
        rin=Signal(bool(0)),
        dout=Signal(intbv(0)[_W32:]),
        vout=Signal(bool(0)),
        lout=Signal(bool(0)),
        rout=Signal(bool(0)),
    )


@block
def _wu_dut(p):
    return axis_width_up(
        p.clk, p.resetn, p.din, p.vin, p.lin, p.rin, p.dout, p.vout, p.lout, p.rout
    )


@block
def _wu_bench(make_dut, p, results):
    dut = make_dut(p)

    @always(delay(5))
    def clkgen():
        p.clk.next = not p.clk

    @instance
    def stim():
        p.resetn.next = 0
        yield p.clk.posedge
        yield p.clk.posedge
        p.resetn.next = 1
        p.rout.next = 1
        p.din.next = 0xBBBB
        p.vin.next = 1
        p.lin.next = 0
        yield p.clk.posedge
        yield delay(1)
        results.append(int(p.vout))
        p.din.next = 0xAAAA
        p.lin.next = 1
        yield p.clk.posedge
        yield delay(1)
        results.append((int(p.vout), int(p.dout), int(p.lout)))
        yield p.clk.posedge
        yield delay(1)
        results.append(int(p.vout))
        raise StopSimulation

    return dut, clkgen, stim


def test_width_up_cosim(hdl_cosim):
    def cosim(p):
        return hdl_cosim(_wu_dut(p), p, "axis_wup_cosim")

    assert _run(cosim, _wu_ports, _wu_bench) == _run(_wu_dut, _wu_ports, _wu_bench)


# -- periodic gate ---------------------------------------------------------


def _pg_ports():
    return SignalView(
        clk=Signal(bool(0)),
        resetn=Signal(bool(0)),
        din=Signal(intbv(0)[_W8:]),
        vin=Signal(bool(0)),
        lin=Signal(bool(0)),
        rin=Signal(bool(0)),
        dout=Signal(intbv(0)[_W8:]),
        vout=Signal(bool(0)),
        lout=Signal(bool(0)),
        rout=Signal(bool(0)),
    )


@block
def _pg_dut(p):
    return axis_periodic_gate(
        p.clk,
        p.resetn,
        p.din,
        p.vin,
        p.lin,
        p.rin,
        p.dout,
        p.vout,
        p.lout,
        p.rout,
        period=2,
    )


@block
def _pg_bench(make_dut, p, results):
    dut = make_dut(p)

    @always(delay(5))
    def clkgen():
        p.clk.next = not p.clk

    @instance
    def stim():
        p.resetn.next = 0
        yield p.clk.posedge
        yield p.clk.posedge
        p.resetn.next = 1
        p.rout.next = 1
        p.din.next = 0x55
        p.vin.next = 1
        p.lin.next = 0
        for _ in range(6):
            yield p.clk.posedge
            yield delay(1)
            results.append(int(p.vout))
        raise StopSimulation

    return dut, clkgen, stim


def test_periodic_gate_cosim(hdl_cosim):
    def cosim(p):
        return hdl_cosim(_pg_dut(p), p, "axis_pg_cosim")

    assert _run(cosim, _pg_ports, _pg_bench) == _run(_pg_dut, _pg_ports, _pg_bench)


# -- packet counter --------------------------------------------------------


def _pc_ports():
    return SignalView(
        clk=Signal(bool(0)),
        resetn=Signal(bool(0)),
        valid=Signal(bool(0)),
        ready=Signal(bool(0)),
        last=Signal(bool(0)),
        beats=Signal(intbv(0)[_W8:]),
        packets=Signal(intbv(0)[_W8:]),
    )


@block
def _pc_dut(p):
    return axis_packet_counter(
        p.clk, p.resetn, p.valid, p.ready, p.last, p.beats, p.packets
    )


@block
def _pc_bench(make_dut, p, results):
    dut = make_dut(p)

    @always(delay(5))
    def clkgen():
        p.clk.next = not p.clk

    @instance
    def stim():
        p.resetn.next = 0
        yield p.clk.posedge
        yield p.clk.posedge
        p.resetn.next = 1
        p.ready.next = 1
        p.valid.next = 1
        p.last.next = 0
        yield p.clk.posedge
        p.last.next = 1
        yield p.clk.posedge
        p.valid.next = 0
        yield p.clk.posedge
        results.append((int(p.beats), int(p.packets)))
        raise StopSimulation

    return dut, clkgen, stim


def test_packet_counter_cosim(hdl_cosim):
    def cosim(p):
        return hdl_cosim(_pc_dut(p), p, "axis_pc_cosim")

    assert _run(cosim, _pc_ports, _pc_bench) == _run(_pc_dut, _pc_ports, _pc_bench)


# -- shared runner ---------------------------------------------------------


def _run(make_dut, ports_factory, bench):
    ports = ports_factory()
    results = []
    bench(make_dut, ports, results).run_sim()
    return results
