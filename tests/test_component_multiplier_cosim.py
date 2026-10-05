"""Verilog cosimulation smoke test for the ``Multiplier`` (Option A)."""

import pytest
from test_component_multiplier_ops import _python_device, _run


def _cosim_device(hdl_cosim, name):
    def _make(mul, ports):
        return hdl_cosim(mul.hdl(ports), ports, name)

    return _make


_CASES = [
    (8, 0x00, 0x00, True, "dsp", None),
    (8, 0xFF, 0x01, True, "dsp", None),
    (8, 0x80, 0x80, False, "dsp", None),
    (8, 0xA5, 0x5A, True, "luts", None),
    (8, 0xFF, 0xFF, True, "luts", None),
    (18, (1 << 17), 0x00003, True, "dsp", None),
    (18, (1 << 18) - 1, (1 << 18) - 1, False, "dsp", None),
    (18, 0x1FFFF, 0x00003, True, "dsp", "9x9"),  # decomposed
    (1, 1, 1, True, "dsp", None),  # smallest signed
    (3, 0b101, 0b011, True, "luts", None),
    (10, 0x3FF, 0x003, True, "dsp", "9x9"),  # ragged top chunk
    (18, 0x3FFFF, 0x00001, False, "dsp", "18x18"),
]


@pytest.mark.parametrize("width,a,b,signed,impl,dsptype", _CASES)
def test_multiplier_cosim_matches_python(width, a, b, signed, impl, dsptype, hdl_cosim):
    python = _run(_python_device, width, a, b, signed, impl, dsptype)
    cosim = _run(
        _cosim_device(hdl_cosim, f"mult_cosim_{width}_{impl}"),
        width,
        a,
        b,
        signed,
        impl,
        dsptype,
    )
    assert cosim == python
