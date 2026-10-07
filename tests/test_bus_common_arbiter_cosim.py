"""Verilog cosimulation smoke tests for the common arbiters (Option A).

The arbiter API uses lists of request/grant signals; MyHDL cannot expose a port
inside a list, so the harness keeps the lists internal and ties them to packed
vector ports with explicit per-element logic (the same pattern as the Wishbone
arbiter).  The same bench drives either the Python block or the converted RTL.
"""

from myhdl import Signal, StopSimulation, always_comb, block, delay, instance, intbv

from myhdl_addons.bus_common.arbiter import (
    fixed_priority_arbiter,
    round_robin_arbiter,
)
from myhdl_addons.common.views import SignalView


@block
def _fixed_top(req_vec, grant_vec):
    req0, req1, req2 = (Signal(bool(0)) for _ in range(3))
    g0, g1, g2 = (Signal(bool(0)) for _ in range(3))
    arb = fixed_priority_arbiter([req0, req1, req2], [g0, g1, g2])

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


@block
def _rr_reset_top(clk, rst, req_vec, grant_vec):
    req0, req1, req2 = (Signal(bool(0)) for _ in range(3))
    g0, g1, g2 = (Signal(bool(0)) for _ in range(3))
    arb = round_robin_arbiter(
        clk, rst, [req0, req1, req2], [g0, g1, g2], reset_active=1
    )

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


@block
def _rr_noreset_top(clk, req_vec, grant_vec):
    req0, req1, req2 = (Signal(bool(0)) for _ in range(3))
    g0, g1, g2 = (Signal(bool(0)) for _ in range(3))
    arb = round_robin_arbiter(
        clk, None, [req0, req1, req2], [g0, g1, g2], reset_active=None
    )

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


def _ports_fixed():
    return SignalView(
        req_vec=Signal(intbv(0)[3:]),
        grant_vec=Signal(intbv(0)[3:]),
    )


@block
def _dut_fixed(ports):
    return _fixed_top(ports.req_vec, ports.grant_vec)


@block
def _fixed_bench(make_dut, ports, vectors, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.req_vec.next = 0
        yield delay(1)
        for req in vectors:
            ports.req_vec.next = req
            yield delay(1)
            results.append(int(ports.grant_vec))
        raise StopSimulation

    return dut, stim


_FIXED_VECTORS = [0b001, 0b010, 0b100, 0b011, 0b101, 0b110, 0b111, 0b000]


def _run_fixed(make_dut):
    ports = _ports_fixed()
    results = []
    _fixed_bench(make_dut, ports, _FIXED_VECTORS, results).run_sim()
    return results


def test_fixed_priority_arbiter_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut_fixed(ports), ports, "bus_fixed_arb_cosim")

    assert _run_fixed(cosim) == _run_fixed(_dut_fixed)


def _ports_rr():
    return SignalView(
        clk=Signal(bool(0)),
        rst=Signal(bool(0)),
        req_vec=Signal(intbv(0)[3:]),
        grant_vec=Signal(intbv(0)[3:]),
    )


@block
def _dut_rr(ports):
    return _rr_reset_top(ports.clk, ports.rst, ports.req_vec, ports.grant_vec)


@block
def _rr_bench(make_dut, ports, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.req_vec.next = 0b111
        ports.rst.next = 1
        ports.clk.next = 1
        yield delay(1)
        results.append(int(ports.grant_vec))
        ports.clk.next = 0
        yield delay(1)
        ports.rst.next = 0
        for _ in range(6):
            ports.clk.next = 1
            yield delay(1)
            results.append(int(ports.grant_vec))
            ports.clk.next = 0
            yield delay(1)
        raise StopSimulation

    return dut, stim


def _run_rr(make_dut):
    ports = _ports_rr()
    results = []
    _rr_bench(make_dut, ports, results).run_sim()
    return results


def test_round_robin_arbiter_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(_dut_rr(ports), ports, "bus_rr_arb_cosim")

    assert _run_rr(cosim) == _run_rr(_dut_rr)


def _ports_rr_noreset():
    return SignalView(
        clk=Signal(bool(0)),
        req_vec=Signal(intbv(0)[3:]),
        grant_vec=Signal(intbv(0)[3:]),
    )


@block
def _dut_rr_noreset(ports):
    return _rr_noreset_top(ports.clk, ports.req_vec, ports.grant_vec)


@block
def _rr_noreset_bench(make_dut, ports, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.req_vec.next = 0b010
        yield delay(1)
        for _ in range(6):
            ports.clk.next = 1
            yield delay(1)
            results.append(int(ports.grant_vec))
            ports.clk.next = 0
            yield delay(1)
        raise StopSimulation

    return dut, stim


def _run_rr_noreset(make_dut):
    ports = _ports_rr_noreset()
    results = []
    _rr_noreset_bench(make_dut, ports, results).run_sim()
    return results


def test_round_robin_arbiter_no_reset_cosim_matches_python(hdl_cosim):
    # no reset -> the pointer needs its converted power-on value
    def cosim(ports):
        return hdl_cosim(
            _dut_rr_noreset(ports),
            ports,
            "bus_rr_arb_nr_cosim",
            initial_values=True,
        )

    assert _run_rr_noreset(cosim) == _run_rr_noreset(_dut_rr_noreset)
