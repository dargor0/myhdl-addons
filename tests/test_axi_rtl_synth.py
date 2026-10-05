"""Yosys synthesizability smoke tests for the AXI RTL blocks (S1).

Each closed system / utility is synthesised with the technology-independent
``synth`` pass; any Yosys error or warning fails the test.
"""

from myhdl import Signal, intbv
from test_axi_rtl_conversion import (
    _axis_top,
    _full_oo_top,
    _full_signals,
    _full_top,
    _lite_top,
)

from myhdl_addons.axi import (
    axis_gate,
    axis_packet_counter,
    axis_periodic_gate,
    axis_register_slice,
    axis_width_down,
    axis_width_up,
)


def _check(hdl_synth, dut, name):
    result = hdl_synth(dut, name)
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report


def test_axi_full_synthesizes(hdl_synth):
    _check(hdl_synth, _full_top(*_full_signals()), "axi_full_synth")


def test_axi_full_oo_synthesizes(hdl_synth):
    _check(hdl_synth, _full_oo_top(*_full_signals()), "axi_full_oo_synth")


def test_axi_lite_synthesizes(hdl_synth):
    dut = _lite_top(
        Signal(bool(0)),  # aclk
        Signal(bool(0)),  # aresetn
        Signal(bool(0)),  # start
        Signal(bool(0)),  # write
        Signal(intbv(0)[16:]),  # addr
        Signal(intbv(0)[32:]),  # wdata
        Signal(intbv(0)[4:]),  # wstrb
        Signal(bool(0)),  # busy
        Signal(bool(0)),  # done
        Signal(intbv(0)[32:]),  # rdata
        Signal(intbv(0)[2:]),  # resp
        Signal(intbv(0)[32:]),  # status_in
        Signal(bool(0)),  # strobes
        Signal(bool(0)),  # observe
    )
    _check(hdl_synth, dut, "axi_lite_synth")


def test_axi_axis_synthesizes(hdl_synth):
    sigs = [Signal(intbv(0)[4:]) for _ in range(10)]
    dut = _axis_top(
        Signal(bool(0)),  # aclk
        Signal(bool(0)),  # aresetn
        Signal(intbv(0)[32:]),  # din
        Signal(bool(0)),  # vin
        Signal(bool(0)),  # lin
        Signal(bool(0)),  # rin
        Signal(intbv(0)[32:]),  # dout
        Signal(bool(0)),  # vout
        Signal(bool(0)),  # lout
        Signal(bool(0)),  # rout
        *sigs,  # sidebands in + out
        Signal(intbv(0)[32:]),  # beats
        Signal(intbv(0)[32:]),  # packets
    )
    _check(hdl_synth, dut, "axi_axis_synth")


def test_axis_register_slice_synthesizes(hdl_synth):
    dut = axis_register_slice(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    _check(hdl_synth, dut, "axis_reg_slice_synth")


def test_axis_gate_synthesizes(hdl_synth):
    dut = axis_gate(
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    _check(hdl_synth, dut, "axis_gate_synth")


def test_axis_periodic_gate_synthesizes(hdl_synth):
    dut = axis_periodic_gate(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        period=4,
    )
    _check(hdl_synth, dut, "axis_periodic_synth")


def test_axis_width_down_synthesizes(hdl_synth):
    dut = axis_width_down(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[8:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    _check(hdl_synth, dut, "axis_wdown_synth")


def test_axis_width_up_synthesizes(hdl_synth):
    dut = axis_width_up(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[8:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
    )
    _check(hdl_synth, dut, "axis_wup_synth")


def test_axis_packet_counter_synthesizes(hdl_synth):
    dut = axis_packet_counter(
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(bool(0)),
        Signal(intbv(0)[32:]),
        Signal(intbv(0)[32:]),
    )
    _check(hdl_synth, dut, "axis_pktcount_synth")
