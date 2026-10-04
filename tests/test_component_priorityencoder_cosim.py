"""Verilog cosimulation smoke test for ``PriorityEncoder`` (Option A)."""

import pytest
from test_component_priorityencoder_encode import _run


def _cosim_device(hdl_cosim, name):
    def _make(encoder, ports):
        return hdl_cosim(encoder.hdl(ports), ports, name)

    return _make


_CASES = [
    (0b0100, 4, "low", None, 0),
    (0b1010, 4, "low", None, 0),
    (0b1010, 4, "high", None, 0),
    (0b0000, 4, "low", None, 0),
    (0b0100, 4, "low", 0, 0),
    (0b0100, 4, "low", 1, 0),
    (0b1000, 4, "low", None, 1),  # registered
]


@pytest.mark.parametrize("din,n,priority,en,registered", _CASES)
def test_priorityencoder_cosim_matches_python(
    din, n, priority, en, registered, hdl_cosim
):
    python = _run(din, n, priority, en, registered)
    cosim = _run(
        din,
        n,
        priority,
        en,
        registered,
        make_device=_cosim_device(hdl_cosim, "pe_cosim"),
    )
    assert cosim == python
