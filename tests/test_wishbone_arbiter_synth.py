"""Yosys synthesizability smoke test for the Wishbone arbiter (S1)."""

from myhdl import Signal, intbv

from test_wishbone_arbiter_conversion import _arb_top


def test_wishbone_arbiter_synthesizes(hdl_synth):
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    result = hdl_synth(_arb_top(req_vec, grant_vec), "wb_arb_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
