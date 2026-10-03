"""Register-file configuration and defined out-of-range reads
(``IC-FR-022..029``)."""

import pytest
from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import HdlConfigError, RegisterFile


def test_as_dict():
    rf = RegisterFile(width=32, depth=32, read_ports=2, write_ports=1)
    info = rf.as_dict()
    assert info["read_ports"] == 2
    assert info["write_ports"] == 1
    assert info["read_latency"] == 0
    assert info["write_mode"] == "read_first"
    assert info["zero_reg_fix_value"] is None
    assert "RegisterFile" in repr(rf)


def test_zero_reg_feature_optional():
    assert RegisterFile(depth=4).as_dict()["zero_reg_fix_value"] is None
    assert (
        RegisterFile(depth=4, zero_reg_fix_value=0).as_dict()["zero_reg_fix_value"] == 0
    )


@block
def _oor_tb(results):
    rf = RegisterFile(width=8, depth=3, read_latency=0)
    ports = rf.ports()
    dut = rf.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.resetn.next = 0
        yield ports.clk.posedge
        ports.resetn.next = 1
        ports.raddr0.next = 3
        yield delay(1)
        results.append(int(ports.rdata0))
        raise StopSimulation

    return clkgen, dut, stim


def test_out_of_range_read_is_zero():
    results = []
    _oor_tb(results).run_sim()
    assert results == [0]


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        RegisterFile(depth=4, init=[1, 2])


def test_configuration_matrix():
    for component in (
        RegisterFile(width=8, depth=4, read_ports=1, write_ports=1),
        RegisterFile(width=8, depth=4, read_latency=1, write_mode="write_first"),
        RegisterFile(
            width=8,
            depth=4,
            read_latency=1,
            write_mode="no_change",
            byte_write=True,
            zero_reg_fix_value=0,
            init=[0, 1, 2, 3],
        ),
    ):
        assert component.hdl(component.ports()) is not None
