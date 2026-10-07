"""Yosys synthesizability smoke tests for ``BranchUnit``/``jalr_target``."""

from myhdl import Signal, intbv

from myhdl_addons.riscv import BranchUnit, jalr_target


def _check(result):
    output = result.stdout + result.stderr
    assert result.returncode == 0, result.report
    assert "ERROR" not in output, output
    assert "Warning" not in output, result.report


def test_branch_unit_synthesizes(hdl_synth):
    comp = BranchUnit(width=32)
    _check(hdl_synth(comp.hdl(comp.ports()), "branch_synth"))


def test_jalr_target_synthesizes(hdl_synth):
    addr_i = Signal(intbv(0)[32:])
    jalr = Signal(bool(0))
    addr_o = Signal(intbv(0)[32:])
    _check(hdl_synth(jalr_target(addr_i, jalr, addr_o), "jalr_target_synth"))
