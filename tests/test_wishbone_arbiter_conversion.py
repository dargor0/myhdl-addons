"""Conversion smoke test for the Wishbone arbiter (Verilog + VHDL).

The arbiter API uses lists of request/grant signals; MyHDL cannot expose a port
inside a list, so the lists are kept internal and tied to packed vector ports.
"""

import pytest
from myhdl import Signal, always_comb, block, intbv

from myhdl_addons.wishbone.arbiter import FixedPriorityArbiter


@block
def _arb_top(req_vec, grant_vec):
    req0, req1, req2 = (Signal(bool(0)) for _ in range(3))
    g0, g1, g2 = (Signal(bool(0)) for _ in range(3))
    arb = FixedPriorityArbiter().block(None, None, [req0, req1, req2], [g0, g1, g2])

    @always_comb
    def unpack_reqs():
        req0.next = req_vec[0]
        req1.next = req_vec[1]
        req2.next = req_vec[2]

    @always_comb
    def pack_grants():
        val = 0
        if g2:
            val = val + 4
        if g1:
            val = val + 2
        if g0:
            val = val + 1
        grant_vec.next = val

    return arb, unpack_reqs, pack_grants


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_fixed_priority_arbiter_converts(hdl, convert_dut):
    req_vec = Signal(intbv(0)[3:])
    grant_vec = Signal(intbv(0)[3:])
    convert_dut(_arb_top(req_vec, grant_vec), hdl, f"wb_arb_{hdl.lower()}")
