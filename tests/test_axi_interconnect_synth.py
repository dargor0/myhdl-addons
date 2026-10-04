"""Yosys synthesizability smoke tests for the AXI fabrics (S1).

Each fabric strategy is elaborated as a closed 2-master / 2-slave system and
synthesised with the technology-independent ``synth`` pass; any Yosys error or
warning fails the test.
"""

from test_axi_interconnect_conversion import (
    _cross_full_top,
    _cross_lite_top,
    _full_signals,
    _lite_signals,
    _shared_full_top,
    _shared_lite_top,
)


def _check(hdl_synth, dut, name):
    result = hdl_synth(dut, name)
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report


def test_axi_shared_bus_lite_synthesizes(hdl_synth):
    _check(hdl_synth, _shared_lite_top(*_lite_signals()), "axi_shared_lite_synth")


def test_axi_crossbar_lite_synthesizes(hdl_synth):
    _check(hdl_synth, _cross_lite_top(*_lite_signals()), "axi_cross_lite_synth")


def test_axi_shared_bus_full_synthesizes(hdl_synth):
    _check(hdl_synth, _shared_full_top(*_full_signals()), "axi_shared_full_synth")


def test_axi_crossbar_full_synthesizes(hdl_synth):
    _check(hdl_synth, _cross_full_top(*_full_signals()), "axi_cross_full_synth")
