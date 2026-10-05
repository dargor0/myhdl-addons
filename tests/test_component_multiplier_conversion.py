"""Conversion smoke test for the ``Multiplier`` component (Verilog + VHDL)."""

import pytest

from myhdl_addons.components import Multiplier


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 8},
        {"width": 8, "signed": False},
        {"width": 8, "impl": "luts"},
        {"width": 8, "impl": "luts", "signed": False},
        {"width": 18, "dsptype": "9x9"},  # decomposed
    ],
)
def test_multiplier_converts(hdl, kwargs, convert_dut):
    comp = Multiplier(**kwargs)
    name = f"mult_{hdl.lower()}_{kwargs.get('impl', 'dsp')}_{kwargs.get('width')}"
    convert_dut(comp.hdl(comp.ports()), hdl, name)
