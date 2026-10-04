"""Yosys synthesizability smoke test for ``Register`` (S1)."""

import pytest

from myhdl_addons.components import Register


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fields": [("q", 8)]},
        {"fields": [("q", 8)], "en": False},
        {"fields": [("q", 8)], "flush": True, "load": True},
        {"fields": [("lo", 4), ("hi", 8)], "en": False},
        {"fields": [("q", 8)], "reset_enable": False, "en": False},
    ],
)
def test_register_synthesizes(kwargs, hdl_synth):
    comp = Register(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "register_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
