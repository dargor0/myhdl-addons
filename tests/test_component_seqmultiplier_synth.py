"""Yosys synthesizability smoke test for ``SequentialMultiplier`` (S1)."""

import pytest

from myhdl_addons.components import SequentialMultiplier


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8},
        {"width": 8, "radix": 4},
        {"width": 8, "signed": False},
        {"width": 8, "en": True},
        {"width": 18, "radix": 4},
    ],
)
def test_seqmultiplier_synthesizes(kwargs, hdl_synth):
    comp = SequentialMultiplier(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "seqmul_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
