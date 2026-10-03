"""Shared pytest fixtures for the component test-suite."""

import pytest


@pytest.fixture
def convert_dut(tmp_path):
    """Return a helper that converts an elaborated block to Verilog and VHDL.

    The generated files are written under a per-test temporary directory and
    discarded automatically; only success/failure of the conversion matters.
    """

    def _convert(dut, hdl, name):
        if hdl == "Verilog":
            dut.convert(hdl="Verilog", path=str(tmp_path), name=name, testbench=False)
        else:
            dut.convert(hdl="VHDL", path=str(tmp_path), name=name)

    return _convert
