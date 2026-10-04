"""Verilog cosimulation smoke test for ``BarrelShifter`` (Option A).

The same ``_shift_tb`` used by the behavioural test drives either the Python
block or the converted Verilog RTL; both must agree.
"""

import pytest
from test_component_barrelshifter_modes import _run

from myhdl_addons.components import ROL, ROR, SLL, SRA, SRL


def _cosim_device(hdl_cosim, name):
    def _make(shifter, ports):
        return hdl_cosim(shifter.hdl(ports), ports, name)

    return _make


_CASES = [
    (8, 0x01, 3, SLL, {}),
    (8, 0x80, 3, SRL, {}),
    (8, 0x80, 3, SRA, {}),
    (8, 0x81, 1, ROL, {}),
    (8, 0x81, 1, ROR, {}),
    (8, 0x01, 10, SLL, {"shamt_bits": 5}),
    (8, 0x80, 10, SRA, {"shamt_mode": "saturate"}),
    (8, 0x80, 10, SRL, {"shamt_mode": "zero", "shamt_bits": 5}),
    (8, 0xA5, 3, ROR, {"structure": "serial"}),
    (8, 0xA5, 3, ROR, {"structure": "two_stage"}),
    (8, 0x01, 0, SLL, {"shamt_const": 2, "modes": ["SLL"]}),
    (8, 0x40, 10, SRA, {"shamt_mode": "saturate", "shamt_bits": 5}),
]


@pytest.mark.parametrize("width,data,shamt,mode,kwargs", _CASES)
def test_barrelshifter_cosim_matches_python(
    width, data, shamt, mode, kwargs, hdl_cosim
):
    python = _run(width, data, shamt, mode, **kwargs)
    cosim = _run(
        width,
        data,
        shamt,
        mode,
        make_device=_cosim_device(hdl_cosim, "sh_cosim"),
        **kwargs,
    )
    assert cosim == python
