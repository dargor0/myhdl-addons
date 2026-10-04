"""Yosys synthesizability smoke test for the Wishbone address decoder (S1)."""

from myhdl import Signal, intbv

from test_wishbone_decoder_conversion import _dec_top


def test_wishbone_decoder_synthesizes(hdl_synth):
    adr = Signal(intbv(0)[16:])
    selects = [Signal(bool(0)) for _ in range(3)]
    result = hdl_synth(_dec_top(adr, *selects), "wb_addrdec_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
