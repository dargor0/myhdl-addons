"""Yosys synthesizability smoke test for ``Decoder`` (S1)."""

import pytest

from myhdl_addons.components import Decoder


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n": 4},
        {"n": 5},
        {"n": 4, "en": True},
        {"n": 4, "registered": 1},
        {"n": 1},
    ],
)
def test_decoder_synthesizes(kwargs, hdl_synth):
    comp = Decoder(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "decoder_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
