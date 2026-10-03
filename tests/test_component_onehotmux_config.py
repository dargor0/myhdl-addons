"""OneHotMux configuration and registered output (``IC-FR-066..068``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import OneHotMux


def test_as_dict():
    mux = OneHotMux(width=8, n=3, valid=True, strict=True)
    info = mux.as_dict()
    assert info["width"] == 8
    assert info["n"] == 3
    assert info["valid"] is True
    assert info["strict"] is True
    assert info["registered"] is False
    assert "OneHotMux" in repr(mux)


def test_combinational_has_no_clock():
    names = OneHotMux(width=8, n=3).ports().names
    assert "clk" not in names
    assert "reset" not in names


def test_registered_ports():
    names = OneHotMux(width=8, n=3, valid=True, registered=True, en=True).ports().names
    assert {"clk", "reset", "en", "valid"}.issubset(names)


@block
def _reg_tb(results):
    mux = OneHotMux(width=8, n=2, valid=True, registered=True, en=True)
    ports = mux.ports()
    dut = mux.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.inputs[0].next = 0xAA
        ports.inputs[1].next = 0xBB
        ports.sel.next = 0b01
        ports.reset.next = 1  # assert reset
        ports.en.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.valid)))
        ports.reset.next = 0  # release
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.valid)))
        ports.sel.next = 0b10
        ports.en.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.y), int(ports.valid)))
        raise StopSimulation

    return clkgen, dut, stim


def test_registered_reset_capture_and_enable():
    results = []
    _reg_tb(results).run_sim()
    assert results == [(0, 0), (0xAA, 1), (0xAA, 1)]


def test_configuration_matrix():
    component = OneHotMux(
        width=8, n=3, valid=True, strict=True, registered=1, en=True
    )
    assert component.hdl(component.ports()) is not None
