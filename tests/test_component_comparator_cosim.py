"""Verilog cosimulation smoke test for ``Comparator`` (Option A)."""

import pytest
from test_component_comparator_outputs import _flags


def _cosim_device(hdl_cosim, name):
    def _make(comparator, ports):
        return hdl_cosim(comparator.hdl(ports), ports, name)

    return _make


_CASES = [
    (8, 5, 3, True),
    (8, 0xFB, 0x03, True),  # -5 < 3
    (8, 0x80, 0x7F, True),  # signed min vs max
    (8, 0xFF, 0x01, True),
    (8, 0xFB, 0x03, False),  # unsigned
    (8, 0x80, 0x01, False),
    (8, 42, 42, True),  # equality
]


@pytest.mark.parametrize("width,a,b,signed", _CASES)
def test_comparator_cosim_matches_python(width, a, b, signed, hdl_cosim):
    python = _flags(width, a, b, signed)
    cosim = _flags(
        width, a, b, signed, make_device=_cosim_device(hdl_cosim, "cmp_cosim")
    )
    assert cosim == python
