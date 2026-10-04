"""Verilog cosimulation smoke test for the Wishbone CSR peripheral (Option A).

The same clocked bench drives either the Python instances or the converted
Verilog RTL bound to an equivalent ``SignalView``; read-back data and the
per-register strobes must match exactly.
"""

from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.common.views import SignalView
from test_wishbone_regfile_conversion import _csr_top


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
        rw_out=Signal(bool(0)),
    )


@block
def _dut(ports):
    return _csr_top(
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
        ports.rw_out,
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
        results.append(("rst", int(ports.busy), int(ports.done)))
        ports.rst.next = 0

        # read ID (0x04)
        ports.req.next = 1
        ports.we.next = 0
        ports.adr.next = 0x04
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("id0", int(ports.busy), int(ports.rw_out)))
        ports.req.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(
            ("id1", int(ports.done), int(ports.err), int(ports.dat_r))
        )

        # write CTRL (0x00) = 0xBEEF
        ports.req.next = 1
        ports.we.next = 1
        ports.adr.next = 0x00
        ports.dat_w.next = 0xBEEF
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("wr0", int(ports.busy), int(ports.rw_out)))
        ports.req.next = 0
        ports.we.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(("wr1", int(ports.done), int(ports.err)))

        # read CTRL back
        ports.req.next = 1
        ports.we.next = 0
        ports.adr.next = 0x00
        ports.sel.next = 0xF
        yield ports.clk.posedge
        yield delay(1)
        results.append(("ctrl0", int(ports.busy), int(ports.rw_out)))
        ports.req.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(
            ("ctrl1", int(ports.done), int(ports.err), int(ports.dat_r))
        )
        raise StopSimulation

    return dut, clkgen, stim


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_wishbone_csr_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut(ports), ports, "wb_csr_cosim")

    assert _run(cosim) == _run(_dut)
