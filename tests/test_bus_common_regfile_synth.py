"""Yosys synthesizability smoke test for the common register/CSR engine."""

from myhdl import Signal, intbv
from test_bus_common_regfile_conversion import _csr_top


def test_register_engine_synthesizes(hdl_synth):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req = Signal(bool(0))
    we = Signal(bool(0))
    addr = Signal(intbv(0)[8:])
    wdata = Signal(intbv(0)[32:])
    wstrb = Signal(intbv(0)[4:])
    rdata = Signal(intbv(0)[32:])
    ack = Signal(bool(0))
    rw_out = Signal(bool(0))
    dut = _csr_top(clk, rst, req, we, addr, wdata, wstrb, rdata, ack, rw_out)
    result = hdl_synth(dut, "bus_csr_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
