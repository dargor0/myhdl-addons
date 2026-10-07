"""Yosys synthesizability smoke test for the common address decoder."""

from myhdl import Signal, intbv
from test_bus_common_addrmap_conversion import _addrdec_top


def test_address_decoder_synthesizes(hdl_synth):
    adr = Signal(intbv(0)[8:])
    sels = [Signal(bool(0)) for _ in range(3)]
    result = hdl_synth(_addrdec_top(adr, *sels), "bus_addrdec_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
