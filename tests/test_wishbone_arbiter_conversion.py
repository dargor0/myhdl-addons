"""Conversion smoke test for the Wishbone arbiter (Verilog + VHDL).

The arbiter API uses lists of request/grant signals; MyHDL cannot expose a port
inside a list, so the lists are kept internal and tied to packed vector ports.
"""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.wishbone.arbiter import FixedPriorityArbiter


@block
def _arb_top(req_vec, grant_vec):
    requests = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]
    arb = FixedPriorityArbiter().block(None, None, requests, grants)

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
    convert_dut(_arb_top(req_vec, grant_vec), hdl, f"wb_arb_{hdl.lower()}")
