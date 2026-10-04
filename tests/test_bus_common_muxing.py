"""Convertible one-hot mux/grant/fanout primitives (CB-FR-050..052).

Behaviour-first tests: every primitive is driven directly and its output
checked; a closed top wrapping them all is converted (Verilog + VHDL),
cosimulated and synthesised.
"""

import pytest
from myhdl import Signal, StopSimulation, always, block, delay, instance, intbv

from myhdl_addons.bus_common.muxing import (
    fanout_gated,
    fanout_plain,
    grant_chain,
    mresp_gated,
    mresp_plain,
    onehot_first,
    onehot_stage,
    or_chain,
    select_chain,
)
from myhdl_addons.common.views import SignalView


@block
def _first_tb(results):
    grant = Signal(bool(0))
    value = Signal(intbv(0)[8:])
    out = Signal(intbv(0)[8:])

    @instance
    def stim():
        grant.next = 1
        value.next = 0xAB
        yield delay(1)
        results.append(int(out))
        grant.next = 0
        yield delay(1)
        results.append(int(out))
        raise StopSimulation

    return onehot_first(grant, value, out), stim


def test_onehot_first():
    results = []
    _first_tb(results).run_sim()
    assert results == [0xAB, 0]


@block
def _stage_tb(results):
    grant = Signal(bool(0))
    value = Signal(intbv(0)[8:])
    acc = Signal(intbv(0)[8:])
    out = Signal(intbv(0)[8:])

    @instance
    def stim():
        acc.next = 0x11
        value.next = 0x22
        grant.next = 1
        yield delay(1)
        results.append(int(out))
        grant.next = 0
        yield delay(1)
        results.append(int(out))
        raise StopSimulation

    return onehot_stage(grant, value, acc, out), stim


def test_onehot_stage():
    results = []
    _stage_tb(results).run_sim()
    assert results == [0x22, 0x11]


@block
def _sc_bool_tb(results):
    grants = [Signal(bool(0)) for _ in range(3)]
    values = [Signal(bool(0)) for _ in range(3)]
    out = Signal(bool(0))

    @instance
    def stim():
        values[0].next = 1
        values[1].next = 0
        values[2].next = 1
        yield delay(1)
        results.append(int(out))
        grants[0].next = 1
        yield delay(1)
        results.append(int(out))
        grants[0].next = 0
        grants[1].next = 1
        yield delay(1)
        results.append(int(out))
        grants[1].next = 0
        grants[2].next = 1
        yield delay(1)
        results.append(int(out))
        raise StopSimulation

    return select_chain(grants, values, out, 0, True), stim


def test_select_chain_bool():
    results = []
    _sc_bool_tb(results).run_sim()
    assert results == [0, 1, 0, 1]


@block
def _sc_intbv_tb(results):
    grants = [Signal(bool(0)) for _ in range(2)]
    values = [Signal(intbv(0)[8:]) for _ in range(2)]
    out = Signal(intbv(0)[8:])

    @instance
    def stim():
        values[0].next = 0x12
        values[1].next = 0x34
        grants[0].next = 1
        yield delay(1)
        results.append(int(out))
        grants[0].next = 0
        grants[1].next = 1
        yield delay(1)
        results.append(int(out))
        grants[1].next = 0
        yield delay(1)
        results.append(int(out))
        raise StopSimulation

    return select_chain(grants, values, out, 8, False), stim


def test_select_chain_intbv():
    results = []
    _sc_intbv_tb(results).run_sim()
    assert results == [0x12, 0x34, 0]


@block
def _sc_single_tb(results):
    grant = Signal(bool(0))
    value = Signal(intbv(0)[4:])
    out = Signal(intbv(0)[4:])

    @instance
    def stim():
        value.next = 0x5
        grant.next = 1
        yield delay(1)
        results.append(int(out))
        grant.next = 0
        yield delay(1)
        results.append(int(out))
        raise StopSimulation

    return select_chain([grant], [value], out, 4, False), stim


def test_select_chain_single():
    results = []
    _sc_single_tb(results).run_sim()
    assert results == [0x5, 0]


@block
def _or_tb(results):
    bits = [Signal(bool(0)) for _ in range(3)]
    out = Signal(bool(0))

    @instance
    def stim():
        for pattern in range(8):
            for i in range(3):
                bits[i].next = (pattern >> i) & 1
            yield delay(1)
            results.append(int(out))
        raise StopSimulation

    return or_chain(bits, out), stim


def test_or_chain():
    results = []
    _or_tb(results).run_sim()
    assert results == [int(p != 0) for p in range(8)]


@block
def _grant_tb(results):
    active = Signal(bool(0))
    owner = Signal(intbv(0, min=0, max=3))
    reqs = [Signal(bool(0)) for _ in range(3)]
    grants = [Signal(bool(0)) for _ in range(3)]

    @instance
    def stim():
        reqs[1].next = 1
        reqs[2].next = 1
        yield delay(1)
        results.append([int(g) for g in grants])
        reqs[1].next = 0
        yield delay(1)
        results.append([int(g) for g in grants])
        active.next = 1
        owner.next = 0
        reqs[2].next = 1
        yield delay(1)
        results.append([int(g) for g in grants])
        raise StopSimulation

    return grant_chain(active, owner, reqs, grants), stim


def test_grant_chain():
    results = []
    _grant_tb(results).run_sim()
    assert results == [[0, 1, 0], [0, 0, 1], [1, 0, 0]]


@block
def _fanout_tb(results):
    src = Signal(bool(0))
    sel = Signal(bool(0))
    dst_g = Signal(bool(0))
    dst_p = Signal(bool(0))

    @instance
    def stim():
        src.next = 1
        sel.next = 1
        yield delay(1)
        results.append((int(dst_g), int(dst_p)))
        sel.next = 0
        yield delay(1)
        results.append((int(dst_g), int(dst_p)))
        src.next = 0
        sel.next = 1
        yield delay(1)
        results.append((int(dst_g), int(dst_p)))
        raise StopSimulation

    return fanout_gated(src, sel, dst_g), fanout_plain(src, dst_p), stim


def test_fanout():
    results = []
    _fanout_tb(results).run_sim()
    assert results == [(1, 1), (0, 1), (0, 0)]


@block
def _mresp_tb(results):
    src = Signal(bool(0))
    grant = Signal(bool(0))
    dst_g = Signal(bool(0))
    dst_p = Signal(bool(0))

    @instance
    def stim():
        src.next = 1
        grant.next = 1
        yield delay(1)
        results.append((int(dst_g), int(dst_p)))
        grant.next = 0
        yield delay(1)
        results.append((int(dst_g), int(dst_p)))
        raise StopSimulation

    return mresp_gated(src, grant, dst_g), mresp_plain(src, dst_p), stim


def test_mresp():
    results = []
    _mresp_tb(results).run_sim()
    assert results == [(1, 1), (0, 1)]


# -- closed top: conversion + cosim + synth --------------------------------


@block
def muxing_top(
    g0,
    g1,
    v0,
    v1,
    sel_out,
    or_a,
    or_b,
    or_out,
    active,
    owner,
    rq0,
    rq1,
    gr0,
    gr1,
    src,
    sel,
    fan_g,
    src2,
    fan_p,
    rsrc,
    rgrant,
    mrg,
    rsrc2,
    mp,
):
    return (
        select_chain([g0, g1], [v0, v1], sel_out, 8, False),
        or_chain([or_a, or_b], or_out),
        grant_chain(active, owner, [rq0, rq1], [gr0, gr1]),
        fanout_gated(src, sel, fan_g),
        fanout_plain(src2, fan_p),
        mresp_gated(rsrc, rgrant, mrg),
        mresp_plain(rsrc2, mp),
    )


def _ports():
    return SignalView(
        g0=Signal(bool(0)),
        g1=Signal(bool(0)),
        v0=Signal(intbv(0)[8:]),
        v1=Signal(intbv(0)[8:]),
        sel_out=Signal(intbv(0)[8:]),
        or_a=Signal(bool(0)),
        or_b=Signal(bool(0)),
        or_out=Signal(bool(0)),
        active=Signal(bool(0)),
        owner=Signal(intbv(0, min=0, max=2)),
        rq0=Signal(bool(0)),
        rq1=Signal(bool(0)),
        gr0=Signal(bool(0)),
        gr1=Signal(bool(0)),
        src=Signal(bool(0)),
        sel=Signal(bool(0)),
        fan_g=Signal(bool(0)),
        src2=Signal(bool(0)),
        fan_p=Signal(bool(0)),
        rsrc=Signal(bool(0)),
        rgrant=Signal(bool(0)),
        mrg=Signal(bool(0)),
        rsrc2=Signal(bool(0)),
        mp=Signal(bool(0)),
    )


@block
def muxing_dut(ports):
    return muxing_top(
        ports.g0,
        ports.g1,
        ports.v0,
        ports.v1,
        ports.sel_out,
        ports.or_a,
        ports.or_b,
        ports.or_out,
        ports.active,
        ports.owner,
        ports.rq0,
        ports.rq1,
        ports.gr0,
        ports.gr1,
        ports.src,
        ports.sel,
        ports.fan_g,
        ports.src2,
        ports.fan_p,
        ports.rsrc,
        ports.rgrant,
        ports.mrg,
        ports.rsrc2,
        ports.mp,
    )


@block
def _bench(make_dut, ports, results):
    dut = make_dut(ports)

    @instance
    def stim():
        ports.v0.next = 0x12
        ports.v1.next = 0x34

        ports.g0.next = 1
        ports.or_a.next = 1
        ports.rq1.next = 1
        ports.src.next = 1
        ports.sel.next = 1
        ports.src2.next = 1
        ports.rsrc.next = 1
        ports.rgrant.next = 1
        ports.rsrc2.next = 1
        yield delay(1)
        results.append(_snap(ports))

        ports.g0.next = 0
        ports.g1.next = 1
        ports.or_a.next = 0
        ports.or_b.next = 1
        ports.rq1.next = 0
        ports.rq0.next = 1
        ports.sel.next = 0
        ports.rgrant.next = 0
        yield delay(1)
        results.append(_snap(ports))

        ports.g1.next = 0
        ports.active.next = 1
        ports.owner.next = 1
        ports.rq0.next = 1
        ports.rq1.next = 1
        yield delay(1)
        results.append(_snap(ports))
        raise StopSimulation

    return dut, stim


def _snap(ports):
    return (
        int(ports.sel_out),
        int(ports.or_out),
        (int(ports.gr0), int(ports.gr1)),
        int(ports.fan_g),
        int(ports.fan_p),
        int(ports.mrg),
        int(ports.mp),
    )


def _run(make_dut):
    ports = _ports()
    results = []
    _bench(make_dut, ports, results).run_sim()
    return results


def test_muxing_behavior():
    results = _run(muxing_dut)
    assert results == [
        (0x12, 1, (0, 1), 1, 1, 1, 1),
        (0x34, 1, (1, 0), 0, 1, 0, 1),
        (0, 1, (0, 1), 0, 1, 0, 1),
    ]


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_muxing_converts(hdl, convert_dut):
    convert_dut(muxing_dut(_ports()), hdl, f"muxing_{hdl.lower()}")


def test_muxing_cosim_matches_python(hdl_cosim):
    def cosim(ports):
        return hdl_cosim(muxing_dut(ports), ports, "muxing_cosim")

    assert _run(cosim) == _run(muxing_dut)


def test_muxing_synthesizes(hdl_synth):
    result = hdl_synth(muxing_dut(_ports()), "muxing_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
