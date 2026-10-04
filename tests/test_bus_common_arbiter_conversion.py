"""Conversion smoke tests for the common arbiters (Verilog + VHDL).

MyHDL does not allow a port to appear in a list, and the arbiter API uses lists
of request/grant signals.  The arbiters are therefore converted embedded with
*internal* request/grant lists, tied to packed vector ports (as a real fabric
would do).
"""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.bus_common.arbiter import (
    fixed_priority_arbiter,
    round_robin_arbiter,
)


@block
def _fixed_top(req_vec, grant_vec):
    requests = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = fixed_priority_arbiter(requests, grants)

    @always_comb
    def unpack_reqs():
        for i in range(3):
            requests[i].next = req_vec[i]

    @always_comb
    def pack_grants():
        val = 0
        bit = 1
        for i in range(3):
            if grants[i]:
                val = val + bit
            bit = bit * 2
        grant_vec.next = val

    return arb, unpack_reqs, pack_grants


@block
def _rr_top_reset(clk, rst, req_vec, grant_vec):
    requests = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = round_robin_arbiter(clk, rst, requests, grants, reset_active=1)

    @always_comb
    def unpack_reqs():
        for i in range(3):
            requests[i].next = req_vec[i]

    @always_comb
    def pack_grants():
        val = 0
        bit = 1
        for i in range(3):
            if grants[i]:
                val = val + bit
            bit = bit * 2
        grant_vec.next = val

    return arb, unpack_reqs, pack_grants


@block
def _rr_top_noreset(clk, req_vec, grant_vec):
    requests = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = round_robin_arbiter(clk, None, requests, grants, reset_active=None)

    @always_comb
    def unpack_reqs():
        for i in range(3):
            requests[i].next = req_vec[i]

    @always_comb
    def pack_grants():
        val = 0
        bit = 1
        for i in range(3):
            if grants[i]:
                val = val + bit
            bit = bit * 2
        grant_vec.next = val

    return arb, unpack_reqs, pack_grants


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_fixed_priority_arbiter_converts(hdl, convert_dut):
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    convert_dut(_fixed_top(req_vec, grant_vec), hdl, f"bus_fixed_arb_{hdl.lower()}")


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_round_robin_arbiter_converts(hdl, convert_dut):
    clk = Signal(bool(0))
    rst = Signal(bool(0))
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    dut = _rr_top_reset(clk, rst, req_vec, grant_vec)
    convert_dut(dut, hdl, f"bus_rr_arb_reset_{hdl.lower()}")


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_round_robin_arbiter_no_reset_converts(hdl, convert_dut):
    clk = Signal(bool(0))
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    dut = _rr_top_noreset(clk, req_vec, grant_vec)
    convert_dut(dut, hdl, f"bus_rr_arb_noreset_{hdl.lower()}")
