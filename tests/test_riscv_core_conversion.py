"""Conversion smoke test for ``RiscvCore`` (``RC-NFR-001``)."""

import pytest
from test_riscv_core import _config, _i, _s, _u

from myhdl_addons.riscv import RiscvCore

_PROGRAM = [_i(1, 0, 0, 1), _u(0x1000, 5), _s(0, 1, 5, 2)]


@pytest.mark.parametrize("hdl", ["Verilog", "VHDL"])
def test_core_converts(hdl, convert_dut, tmp_path):
    comp = RiscvCore(_config(tmp_path, _PROGRAM))
    convert_dut(comp.hdl(comp.ports()), hdl, f"core_{hdl.lower()}")
