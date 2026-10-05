"""Verilog cosimulation smoke test for ``SequentialMultiplier`` (Option A)."""

import pytest
from test_component_seqmultiplier_ops import _python_device, _run


def _cosim_device(hdl_cosim, name):
    def _make(mul, ports):
        return hdl_cosim(mul.hdl(ports), ports, name)

    return _make


_CASES = [
    (8, 0x03, 0x04, True, 2, False),
    (8, 0xFF, 0x01, True, 2, False),
    (8, 0x80, 0x80, True, 4, False),
    (8, 0xA5, 0x5A, False, 4, False),
    (8, 0xFF, 0xFF, True, 2, True),  # with en
    (18, (1 << 17), 0x00003, True, 4, False),
]


@pytest.mark.parametrize("width,a,b,signed,radix,en", _CASES)
def test_seqmultiplier_cosim_matches_python(width, a, b, signed, radix, en, hdl_cosim):
    python = _run(_python_device, width, a, b, signed, radix, en)
    cosim = _run(
        _cosim_device(hdl_cosim, f"seqmul_cosim_{width}_{radix}"),
        width,
        a,
        b,
        signed,
        radix,
        en,
    )
    assert cosim == python
