"""Yosys synthesizability smoke tests for the common arbiters."""

from myhdl import Signal, intbv
from test_bus_common_arbiter_cosim import (
    _fixed_top,
    _rr_noreset_top,
    _rr_reset_top,
)


def _check(result):
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report


def test_fixed_priority_arbiter_synthesizes(hdl_synth):
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    _check(hdl_synth(_fixed_top(req_vec, grant_vec), "bus_fixed_arb_synth"))


def test_round_robin_arbiter_synthesizes(hdl_synth):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    _check(hdl_synth(_rr_reset_top(clk, rst, req_vec, grant_vec), "bus_rr_arb_synth"))


def test_round_robin_arbiter_no_reset_synthesizes(hdl_synth):
    clk = Signal(bool(0))
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    _check(hdl_synth(_rr_noreset_top(clk, req_vec, grant_vec), "bus_rr_arb_nr_synth"))
