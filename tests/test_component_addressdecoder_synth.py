"""Yosys synthesizability smoke test for ``AddressDecoder`` (S1)."""

import pytest

from myhdl_addons.components import AddressDecoder


@pytest.mark.parametrize(
    "config",
    [
        {"adr_width": 8, "windows": ((0, 4),)},
        {"adr_width": 8, "windows": ((0, 4), (8, 4)), "en": True, "valid": True},
        {
            "adr_width": 16,
            "windows": ((0x0000, 0x100), (0x1000, 0x100)),
            "registered": 1,
            "en": True,
        },
        {
            "adr_width": 8,
            "windows": ((0, 1), (2, 1), (4, 1), (6, 1), (8, 1)),
            "valid": True,
        },
    ],
)
def test_addressdecoder_synthesizes(config, hdl_synth):
    comp = AddressDecoder(**config)
    result = hdl_synth(comp.hdl(comp.ports()), "addressdecoder_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
