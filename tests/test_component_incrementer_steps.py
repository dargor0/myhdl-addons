"""Incrementer stepping semantics (``IC-FR-040..047``)."""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import Incrementer


@block
def _python_device(inc, ports):
    return inc.hdl(ports)


@block
def _inc_tb(
    make_device,
    results,
    width,
    steps,
    load_enable,
    wrap_mode,
    carry,
    a,
    en,
    sel,
    load,
    load_value,
):
    inc = Incrementer(
        width=width,
        steps=steps,
        load_enable=load_enable,
        wrap_mode=wrap_mode,
        carry=carry,
    )
    ports = inc.ports()
    dut = make_device(inc, ports)
    has_sel = len(inc.as_dict()["steps"]) > 1
    step_sel_sig = ports.signals.get("step_sel")
    load_sig = ports.signals.get("load")
    load_value_sig = ports.signals.get("load_value")
    carry_sig = ports.signals.get("carry")

    @instance
    def stim():
        # Drive a known-different state first: a converted combinational DUT
        # is not re-evaluated by cosimulation when no input changes.
        ports.a.next = 0
        ports.en.next = 0
        if has_sel:
            step_sel_sig.next = 0
        if load_enable:
            load_sig.next = 0
            load_value_sig.next = 0
        yield delay(1)
        ports.a.next = a
        ports.en.next = en
        if has_sel:
            step_sel_sig.next = sel
        if load_enable:
            load_sig.next = load
            load_value_sig.next = load_value
        yield delay(1)
        results.append(
            (int(ports.y), int(carry_sig) if carry_sig is not None else None)
        )
        raise StopSimulation

    return dut, stim


def _run(
    width=8,
    a=0,
    en=1,
    sel=0,
    load=0,
    load_value=0,
    make_device=_python_device,
    **kwargs,
):
    results = []
    _inc_tb(
        make_device,
        results,
        width,
        kwargs.get("steps"),
        kwargs.get("load_enable", True),
        kwargs.get("wrap_mode", "wrap"),
        kwargs.get("carry", False),
        a,
        en,
        sel,
        load,
        load_value,
    ).run_sim()
    return results[0]


def test_single_step():
    assert _run(a=5)[0] == 6


@pytest.mark.parametrize(
    ("sel", "expect"),
    [(0, 7), (1, 9), (2, 3), (3, 1)],
)
def test_coded_step_selection(sel, expect):
    y, _ = _run(a=5, steps=(2, 4, -2, -4), sel=sel)
    assert y == expect


def test_load_overrides():
    y, _ = _run(a=5, load=1, load_value=0xAB)
    assert y == 0xAB


def test_enable_holds():
    y, _ = _run(a=5, en=0)
    assert y == 5


def test_wrap_and_saturate():
    assert _run(a=0xFF, steps=(1,), wrap_mode="wrap")[0] == 0x00
    y, carry = _run(a=0xFF, steps=(1,), wrap_mode="saturate", carry=True)
    assert y == 0xFF
    assert carry == 1
    assert _run(a=0x00, steps=(-1,), wrap_mode="saturate")[0] == 0x00
    assert _run(a=0x00, steps=(-1,), wrap_mode="wrap")[0] == 0xFF


def test_out_of_range_selector_holds():
    y, _ = _run(a=5, steps=(3, 4, 5), sel=3)
    assert y == 5


def test_carry_wrap():
    y, carry = _run(a=0xFF, steps=(1,), wrap_mode="wrap", carry=True)
    assert (y, carry) == (0x00, 1)


def test_load_disabled_behaviour():
    assert _run(a=5, steps=(1,), load_enable=False) == (6, None)
    assert _run(a=5, steps=(1,), en=0, load_enable=False) == (5, None)
    y, carry = _run(a=0xFF, steps=(1,), load_enable=False, carry=True)
    assert (y, carry) == (0x00, 1)
