"""``MuxTree`` selection semantics (``IC-FR-096..099``).

Behaviour-first: every ``sel`` code and the out-of-range codes are checked
against a Python reference for **all four policies** (``const``, ``lastinput``,
``alias``, ``wrap``), over boundary operands, power-of-two and non-power-of-two
``n`` (incl. ``n == 1``), and ``alias``/``default_value`` boundaries.  ``_bench``
is reused by the cosimulation test so the same stimulus drives both the Python
block and the converted RTL.
"""

import pytest
from myhdl import StopSimulation, block, delay, instance

from myhdl_addons.components import HdlConfigError, MuxTree


@block
def _bench(make_device, width, n, policy, default_value, alias, vectors, results):
    comp = MuxTree(
        width=width, n=n, policy=policy, default_value=default_value, alias=alias
    )
    ports = comp.ports()
    dut = make_device(comp, ports)

    # ``n == 1`` has no ``sel``; reference it only in the variant that has one.
    if "sel" in ports:

        @instance
        def stim():
            for sel, values in vectors:
                for i, value in enumerate(values):
                    ports[f"in{i}"].next = value
                ports.sel.next = sel
                yield delay(1)
                results.append(int(ports.y))
            raise StopSimulation

    else:

        @instance
        def stim():
            for sel, values in vectors:
                for i, value in enumerate(values):
                    ports[f"in{i}"].next = value
                yield delay(1)
                results.append(int(ports.y))
            raise StopSimulation

    return dut, stim


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


# width, n, policy, default_value, alias, per-input values
_CASES = [
    # --- non-power-of-two, all four policies ---
    (8, 3, "const", 0xAB, 0, [0x11, 0x22, 0x33]),
    (8, 3, "lastinput", 0, 0, [0x11, 0x22, 0x33]),
    (8, 3, "alias", 0, 0, [0x11, 0x22, 0x33]),  # alias = 0
    (8, 3, "alias", 0, 2, [0x11, 0x22, 0x33]),  # alias = n-1
    (8, 3, "wrap", 0, 0, [0x11, 0x22, 0x33]),
    (8, 5, "const", 0xAB, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 5, "lastinput", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 5, "alias", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),  # alias = 0
    (8, 5, "alias", 0, 4, [0x11, 0x22, 0x33, 0x44, 0x55]),  # alias = n-1
    (8, 5, "wrap", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55]),
    (8, 6, "const", 0xAB, 0, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]),
    (8, 6, "wrap", 0, 0, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66]),  # pad = 2
    (8, 7, "lastinput", 0, 0, [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7]),
    (8, 7, "wrap", 0, 0, [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7]),  # pad = 1
    (8, 9, "wrap", 0, 0, [1, 2, 3, 4, 5, 6, 7, 8, 9]),  # pad = 7 (large)
    (8, 11, "lastinput", 0, 0, list(range(1, 12))),  # pad = 5
    # --- power-of-two (policy irrelevant) ---
    (8, 2, "lastinput", 0, 0, [0x11, 0x22]),
    (8, 4, "lastinput", 0xAB, 0, [0x00, 0xFF, 0x80, 0x7F]),
    (8, 8, "wrap", 0xAB, 0, [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]),
    # --- width / default_value boundaries ---
    (4, 3, "const", 0xF, 0, [0x1, 0x2, 0x3]),  # default = all-ones
    (4, 3, "const", 0x1FF, 0, [0x1, 0x2, 0x3]),  # default masked to 0xF
    (1, 5, "lastinput", 0, 0, [0x1, 0x0, 0x1, 0x0, 0x1]),
    (8, 1, "lastinput", 0, 0, [0x5A]),  # n == 1: no select
]


def _vectors(n, values):
    return [(sel, values) for sel in range(1 << MuxTree(n=n).sel_bits)]


def _expected(sel, values, n, width, policy, default_value, alias):
    if sel < n:
        return values[sel]
    if policy == "const":
        return default_value & ((1 << width) - 1)
    if policy == "lastinput":
        return values[n - 1]
    if policy == "alias":
        return values[alias]
    return values[sel % n]  # wrap


def _run(make_device, width, n, policy, default_value, alias, vectors):
    results = []
    _bench(
        make_device, width, n, policy, default_value, alias, vectors, results
    ).run_sim()
    return results


@pytest.mark.parametrize("width,n,policy,default_value,alias,values", _CASES)
def test_muxtree_selects_every_code(width, n, policy, default_value, alias, values):
    vectors = _vectors(n, values)
    results = _run(_python_device, width, n, policy, default_value, alias, vectors)
    expected = [
        _expected(sel, values, n, width, policy, default_value, alias)
        for sel, _ in vectors
    ]
    assert results == expected


@pytest.mark.parametrize(
    "n,bits", [(1, 0), (2, 1), (3, 2), (4, 2), (5, 3), (8, 3), (9, 4), (16, 4)]
)
def test_muxtree_sel_bits(n, bits):
    assert MuxTree(n=n).sel_bits == bits


def test_muxtree_ports():
    ports = MuxTree(width=8, n=5).ports()
    assert ports.names[:5] == ["in0", "in1", "in2", "in3", "in4"]
    assert "sel" in ports and "y" in ports
    assert len(ports.sel) == 3
    assert len(ports.y) == 8
    # n == 1 is a power of two: no select at all
    assert "sel" not in MuxTree(width=8, n=1).ports()


def test_muxtree_policy_required_only_for_non_power_of_two():
    with pytest.raises(HdlConfigError):
        MuxTree(width=8, n=3, policy=None)
    # power of two: policy may be omitted (None)
    MuxTree(width=8, n=4, policy=None)
    MuxTree(width=8, n=1, policy=None)


def test_muxtree_alias_validated_only_when_used():
    # non-power-of-two + alias policy: index must be in range
    with pytest.raises(HdlConfigError):
        MuxTree(width=8, n=5, policy="alias", alias=5)
    with pytest.raises(HdlConfigError):
        MuxTree(width=8, n=5, policy="alias", alias=-1)
    # power of two: no holes, alias is irrelevant and not validated
    MuxTree(width=8, n=4, policy="alias", alias=99)


def test_muxtree_rejects_bad_config():
    with pytest.raises(HdlConfigError):
        MuxTree(width=0)
    with pytest.raises(HdlConfigError):
        MuxTree(width=8, n=0)
    with pytest.raises(HdlConfigError):
        MuxTree(width=8, n=3, policy="bogus")
    with pytest.raises(HdlConfigError):
        MuxTree(width=8, n=2, default_value=-1)
