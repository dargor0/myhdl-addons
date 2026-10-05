"""Verilog cosimulation smoke test for master + slave + point-to-point (Option A).

The closed system (master, slave, interconnect) is elaborated once; the same
clocked bench drives either the Python instances or the converted Verilog RTL
bound to an equivalent ``SignalView``.  A per-phase trace of the external
command/status/strobe signals must match exactly.
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv
from test_wishbone_p2p_conversion import _p2p_top

from myhdl_addons.common.views import SignalView


def _ports():
    return SignalView(
        clk=Signal(bool(0)),
        rst=Signal(bool(0)),
        req=Signal(bool(0)),
        adr=Signal(intbv(0)[16:]),
        we=Signal(bool(0)),
        dat_w=Signal(intbv(0)[32:]),
        sel=Signal(intbv(0)[4:]),
        busy=Signal(bool(0)),
        done=Signal(bool(0)),
        dat_r=Signal(intbv(0)[32:]),
        err=Signal(bool(0)),
        wr=Signal(bool(0)),
        rd=Signal(bool(0)),
        wr_data=Signal(intbv(0)[32:]),
        wr_sel=Signal(intbv(0)[4:]),
    )


@block
def _dut(ports):
    return _p2p_top(
        ports.clk,
        ports.rst,
        ports.req,
        ports.adr,
        ports.we,
        ports.dat_w,
        ports.sel,
        ports.busy,
        ports.done,
        ports.dat_r,
        ports.err,
        ports.wr,
        ports.rd,
        ports.wr_data,
        ports.wr_sel,
    )


@block
def _bench(make_dut, ports, results):
    dut = make_dut(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.rst.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append(("rst", int(ports.busy), int(ports.done), int(ports.err)))
        ports.rst.next = 0

        # write 0xCAFE to 0x0020
        ports.req.next = 1
        ports.we.next = 1
        ports.adr.next = 0x20
        ports.dat_w.next = 0xCAFE
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(
            (
                "w0",
                int(ports.busy),
                int(ports.wr),
                int(ports.wr_data),
                int(ports.wr_sel),
            )
        )
        ports.req.next = 0
        ports.we.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(
            ("w1", int(ports.busy), int(ports.done), int(ports.err), int(ports.wr))
        )

        # read 0x0020
        ports.req.next = 1
        ports.we.next = 0
        ports.adr.next = 0x20
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("r0", int(ports.busy), int(ports.rd)))
        ports.req.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(
            (
                "r1",
                int(ports.busy),
                int(ports.done),
                int(ports.err),
                int(ports.dat_r),
                int(ports.rd),
            )
        )
        raise StopSimulation

    return dut, clkgen, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_wishbone_p2p_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "wb_p2p_cosim")

    assert _run(cosim) == _run(_dut)
