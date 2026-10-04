"""Verilog cosimulation smoke test for ``Decoder`` (Option A)."""

import pytest
from test_component_decoder_decode import _run


def _cosim_device(hdl_cosim, name):
    def _make(decoder, ports):
        return hdl_cosim(decoder.hdl(ports), ports, name)

    return _make


_CASES = [
    (0, 4, None, 0),
    (1, 4, None, 0),
    (2, 4, None, 0),
    (3, 4, None, 0),
    (3, 3, None, 0),  # out of range
    (1, 4, 0, 0),
    (1, 4, 1, 0),
    (2, 4, None, 1),  # registered
]


@pytest.mark.parametrize("sel,n,en,registered", _CASES)
def test_decoder_cosim_matches_python(sel, n, en, registered, hdl_cosim):
    python = _run(sel, n, en, registered)
    cosim = _run(
        sel, n, en, registered, make_device=_cosim_device(hdl_cosim, "dec_cosim")
    )
    assert cosim == python
