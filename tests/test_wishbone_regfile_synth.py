"""Yosys synthesizability smoke test for the Wishbone CSR peripheral (S1)."""

from myhdl import Signal, intbv
from test_wishbone_regfile_conversion import _csr_top


def test_wishbone_csr_synthesizes(hdl_synth):
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
    rw_out = Signal(bool(0))
    dut = _csr_top(clk, rst, req, adr, we, dat_w, sel, busy, done, dat_r, err, rw_out)
    result = hdl_synth(dut, "wb_csr_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
