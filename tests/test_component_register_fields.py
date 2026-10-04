"""Register capture, control priority and multi-field bundling
(``IC-FR-130..137``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Register


@block
def _python_device(reg, ports):
    return reg.hdl(ports)


@block
def _capture_tb(make_device, results):
    reg = Register(fields=[("q", 8)], en=True, reset_values={"q": 0})
    ports = reg.ports()
    dut = make_device(reg, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        ports.en.next = 1
        ports.d_q.next = 0xAA
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        ports.reset.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        ports.en.next = 0
        ports.d_q.next = 0x55
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        raise StopSimulation

    return clkgen, dut, stim


def test_capture_reset_and_enable():
    results = []
    _capture_tb(_python_device, results).run_sim()
    assert results == [0, 0xAA, 0xAA]


@block
def _control_tb(make_device, results):
    reg = Register(
        fields=[("q", 8)],
        en=True,
        flush=True,
        load=True,
        reset_values={"q": 0x00},
        flush_values={"q": 0xF0},
        load_values={"q": 0x0F},
    )
    ports = reg.ports()
    dut = make_device(reg, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 1
        ports.en.next = 1
        ports.d_q.next = 0xAB
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        ports.load.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        ports.load.next = 0
        ports.flush.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        ports.flush.next = 0
        ports.reset.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.q_q))
        raise StopSimulation

    return clkgen, dut, stim


def test_control_priority():
    results = []
    _control_tb(_python_device, results).run_sim()
    assert results == [0xAB, 0x0F, 0xF0, 0x00]


@block
def _multi_tb(make_device, results):
    reg = Register(fields=[("lo", 4), ("hi", 8)], en=False)
    ports = reg.ports()
    dut = make_device(reg, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.q_lo), int(ports.q_hi)))
        ports.reset.next = 1
        ports.d_lo.next = 0xA
        ports.d_hi.next = 0x5A
        yield ports.clk.posedge
        yield delay(1)
        results.append((int(ports.q_lo), int(ports.q_hi)))
        raise StopSimulation

    return clkgen, dut, stim


def test_multi_field_bundling():
    results = []
    _multi_tb(_python_device, results).run_sim()
    assert results == [(0, 0), (0xA, 0x5A)]


def test_configuration():
    reg = Register(fields=[("q", 8)], en=False, flush=True)
    assert "en" not in reg.ports().names
    assert "flush" in reg.ports().names
    info = reg.as_dict()
    assert info["fields"] == (("q", 8),)
    assert "Register" in repr(reg)
