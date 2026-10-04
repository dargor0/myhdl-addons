"""Yosys synthesizability smoke test for ``Comparator`` (S1)."""

import pytest

from myhdl_addons.components import Comparator


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8, "signed": True},
        {"width": 8, "signed": False},
        {"width": 8, "outputs": ("eq", "ltu")},
        {"width": 8, "registered": True},
        {"width": 8, "registered": True, "en": True, "outputs": ("eq", "ne", "ltu")},
    ],
)
def test_comparator_synthesizes(kwargs, hdl_synth):
    comp = Comparator(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "comparator_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
