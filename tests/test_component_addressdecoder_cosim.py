"""Verilog cosimulation smoke test for ``AddressDecoder`` (Option A).

The same ``_ad_tb`` used by the behavioural test drives either the Python
block or the converted Verilog RTL; both must agree.
"""

import pytest
from test_component_addressdecoder_decode import _WINDOWS, _run


def _cosim_device(hdl_cosim, name):
    def _make(dec, ports):
        return hdl_cosim(dec.hdl(ports), ports, name)

    return _make


_CASES = [
    ({"adr_width": 8, "windows": _WINDOWS}, 0x00, None, False),
    ({"adr_width": 8, "windows": _WINDOWS}, 0x20, None, False),
    ({"adr_width": 8, "windows": _WINDOWS}, 0x10, None, False),
    ({"adr_width": 8, "windows": _WINDOWS, "en": True}, 0x20, 0, True),
    ({"adr_width": 8, "windows": _WINDOWS, "en": True}, 0x20, 1, True),
    ({"adr_width": 8, "windows": ((0x20, 0x10),)}, 0x2F, None, False),
    ({"adr_width": 8, "windows": _WINDOWS, "registered": 1}, 0x20, None, True),
]


@pytest.mark.parametrize("config,adr,en,sample_valid", _CASES)
def test_addressdecoder_cosim_matches_python(config, adr, en, sample_valid, hdl_cosim):
    python = _run(config, adr, en, sample_valid)
    cosim = _run(
        config,
        adr,
        en,
        sample_valid,
        make_device=_cosim_device(hdl_cosim, "ad_cosim"),
    )
    assert cosim == python
