"""Yosys synthesizability smoke test for master + slave + point-to-point (S1)."""

from myhdl import Signal, intbv
from test_wishbone_p2p_conversion import _p2p_top


def test_wishbone_p2p_synthesizes(hdl_synth):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req = Signal(bool(0))
    adr = Signal(intbv(0)[16:])
    we = Signal(bool(0))
    dat_w = Signal(intbv(0)[32:])
    sel = Signal(intbv(0)[4:])
    busy = Signal(bool(0))
    done = Signal(bool(0))
    dat_r = Signal(intbv(0)[32:])
    err = Signal(bool(0))
    wr = Signal(bool(0))
    rd = Signal(bool(0))
    wr_data = Signal(intbv(0)[32:])
    wr_sel = Signal(intbv(0)[4:])
    dut = _p2p_top(
        clk,
        rst,
        req,
        adr,
        we,
        dat_w,
        sel,
        busy,
        done,
        dat_r,
        err,
        wr,
        rd,
        wr_data,
        wr_sel,
    )
    result = hdl_synth(dut, "wb_p2p_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
