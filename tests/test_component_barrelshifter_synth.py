"""Yosys synthesizability smoke test for ``BarrelShifter`` (S1)."""

import pytest

from myhdl_addons.components import ROL, ROR, SLL, SRA, SRL, BarrelShifter


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8},
        {"width": 8, "modes": [SLL, SRL, SRA, ROL, ROR], "structure": "serial"},
        {"width": 8, "structure": "two_stage", "shamt_bits": 5},
        {"width": 8, "shamt_const": 3, "modes": ["SLL", "SRA"]},
        {"width": 8, "shamt_mode": "saturate", "shamt_bits": 5},
        {"width": 8, "shamt_mode": "zero", "shamt_bits": 5, "registered": 1},
    ],
)
def test_barrelshifter_synthesizes(kwargs, hdl_synth):
    comp = BarrelShifter(**kwargs)
    result = hdl_synth(comp.hdl(comp.ports()), "barrelshifter_synth")
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report
