"""ALU registered output and configuration (``IC-FR-018..019``, ``IC-FR-128``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Alu


def test_combinational_has_no_clock():
    ports = Alu(width=8).ports()
    assert "clk" not in ports.names
    assert "reset" not in ports.names


def test_registered_ports_and_dict():
    alu = Alu(width=8, ops=["ADD", "SUB"], registered=1, en=True)
    ports = alu.ports()
    assert {"clk", "reset", "en"}.issubset(ports.names)
    info = alu.as_dict()
    assert info["registered"] == 1
    assert set(info["ops"]) == {"NOP", "ADD", "SUB"}


@block
def _alu_reg_tb(results):
    alu = Alu(width=8, ops=["ADD"], flags=["zero"], registered=1, en=True)
    ports = alu.ports()
    dut = alu.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.reset.next = 0
        ports.en.next = 1
        ports.a.next = 10
        ports.b.next = 5
        ports.op.next = alu.get_op_intmap()["ADD"]
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        ports.en.next = 0
        ports.a.next = 20
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.y))
        raise StopSimulation

    return clkgen, dut, stim


def test_registered_alu_reset_and_enable():
    results = []
    _alu_reg_tb(results).run_sim()
    assert results == [0, 15, 15]
