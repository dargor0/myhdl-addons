"""Comparator configuration and registered output (``IC-FR-051..056``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Comparator


def test_as_dict():
    comparator = Comparator(width=16, outputs=("eq", "lt"), signed=False)
    info = comparator.as_dict()
    assert info["width"] == 16
    assert info["outputs"] == ("eq", "lt")
    assert info["signed"] is False
    assert info["registered"] is False
    assert "Comparator" in repr(comparator)


def test_combinational_has_no_clock():
    names = Comparator(width=8).ports().names
    assert "clk" not in names
    assert "reset" not in names


def test_registered_ports():
    names = Comparator(width=8, registered=True, en=True).ports().names
    assert {"clk", "reset", "en"}.issubset(names)


@block
def _reg_tb(results):
    comparator = Comparator(
        width=8, outputs=("eq", "lt"), signed=True, registered=True, en=True
    )
    ports = comparator.ports()
    dut = comparator.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 1  # assert reset
        ports.en.next = 1
        ports.a.next = 5
        ports.b.next = 3
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.eq), int(ports.lt)))
        ports.reset.next = 0  # release
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.eq), int(ports.lt)))
        ports.a.next = 3
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.eq), int(ports.lt)))
        ports.en.next = 0
        ports.a.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.eq), int(ports.lt)))
        raise StopSimulation

    return clkgen, dut, stim


def test_registered_reset_capture_and_enable():
    results = []
    _reg_tb(results).run_sim()
    assert results == [(0, 0), (0, 0), (1, 0), (1, 0)]


def test_configuration_matrix():
    component = Comparator(
        width=8,
        outputs=("eq", "ne", "lt", "ltu", "gt", "gtu", "ge", "le"),
        signed=False,
        registered=1,
        en=True,
    )
    assert component.hdl(component.ports()) is not None
