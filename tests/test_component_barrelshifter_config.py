"""Barrel shifter structure/registered configuration (``IC-FR-034..039``)."""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import SLL, SRA, BarrelShifter, HdlConfigError


def test_shamt_width_derivation():
    assert BarrelShifter(width=16).shamt_bits == 4
    assert BarrelShifter(width=16, shamt_mode="saturate").shamt_width == 5
    assert BarrelShifter(width=16, shamt_bits=7).shamt_bits == 7


def test_as_dict():
    shifter = BarrelShifter(width=16, modes=["SLL", "SRA"], structure="two_stage")
    info = shifter.as_dict()
    assert info["width"] == 16
    assert info["structure"] == "two_stage"
    assert info["modes"] == (SLL, SRA)
    assert "BarrelShifter" in repr(shifter)


@block
def _reg_tb(results):
    shifter = BarrelShifter(width=8, modes=["SLL"], registered=1, en=True)
    ports = shifter.ports()
    dut = shifter.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0  # assert reset
        ports.mode.next = SLL
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.reset.next = 1  # release
        ports.en.next = 1
        ports.data.next = 0x01
        ports.shamt.next = 3
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.en.next = 0
        ports.data.next = 0x02
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return clkgen, dut, stim


def test_registered_shifter_reset_and_enable():
    results = []
    _reg_tb(results).run_sim()
    assert results == [0, 0x08, 0x08]


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        BarrelShifter(structure="sideways")


def test_configuration_matrix():
    for component in (
        BarrelShifter(width=8),
        BarrelShifter(
            width=8,
            structure="two_stage",
            shamt_mode="saturate",
            registered=1,
            en=True,
            modes=["SLL", "SRA"],
        ),
        BarrelShifter(
            width=8,
            structure="serial",
            shamt_mode="zero",
            shamt_bits=5,
            shamt_const=3,
            registered=1,
        ),
    ):
        assert component.hdl(component.ports()) is not None
