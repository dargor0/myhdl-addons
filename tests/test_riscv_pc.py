"""``ProgramCounter`` sequencing, load and link values (``RC-FR-029``)."""

from myhdl import ResetSignal, StopSimulation, always, block, delay, instance

from myhdl_addons.riscv import ProgramCounter

_WIDTH = 32
_MASK = (1 << _WIDTH) - 1


@block
def _python_device(comp, ports):
    return comp.hdl(ports)


@block
def _pc_tb(make_device, results, reset_value, actions):
    comp = ProgramCounter(reset_value=reset_value)
    ports = comp.ports()
    dut = make_device(comp, ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        for action in actions:
            for name, value in action["set"].items():
                getattr(ports, name).next = value
            yield delay(1)
            if action.get("link"):
                results.append(("link", int(ports.link_value)))
            if action.get("edge"):
                yield ports.clk.posedge
                yield delay(1)
                results.append(("pc", int(ports.pc)))
        raise StopSimulation

    return clkgen, dut, stim


def _model(actions, reset_value, width=_WIDTH):
    mask = (1 << width) - 1
    pc = reset_value & mask
    out = []
    for action in actions:
        fields = action["set"]
        step = 2 if fields["compressed"] else 4
        if action.get("link"):
            out.append(("link", (pc + step) & mask))
        if action.get("edge"):
            pc = (fields["next_pc"] & mask) if fields["load"] else (pc + step) & mask
            out.append(("pc", pc))
    return out


def _actions():
    return [
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "link": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "edge": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "edge": True, "link": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 1}, "edge": True, "link": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 1}, "edge": True},
        {"set": {"load": 1, "next_pc": 0x20000000, "compressed": 0}, "edge": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "edge": True, "link": True},
        {"set": {"load": 1, "next_pc": 0xFFFFFFFC, "compressed": 0}, "edge": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "edge": True, "link": True},
    ]


def _run(make_device, reset_value, actions):
    results = []
    _pc_tb(make_device, results, reset_value, actions).run_sim()
    return results


def test_program_counter_matches_model():
    reset_value = 0x1000
    actions = _actions()
    assert _run(_python_device, reset_value, actions) == _model(actions, reset_value)


def test_program_counter_reset_value():
    actions = [{"set": {"load": 0, "next_pc": 0, "compressed": 0}, "link": True}]
    assert _run(_python_device, 0xDEADB000, actions) == _model(actions, 0xDEADB000)


def test_program_counter_wraps():
    reset_value = 0xFFFFFFFE
    actions = [
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "edge": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "edge": True},
    ]
    assert _run(_python_device, reset_value, actions) == _model(actions, reset_value)
    assert [value for _, value in _run(_python_device, reset_value, actions)] == [
        0x00000002,
        0x00000006,
    ]


def test_program_counter_link_steps():
    # link = pc + 4 (32-bit) or pc + 2 (compressed)
    actions = [
        {"set": {"load": 0, "next_pc": 0, "compressed": 0}, "link": True},
        {"set": {"load": 0, "next_pc": 0, "compressed": 1}, "link": True},
    ]
    results = _run(_python_device, 0x100, actions)
    assert results == [("link", 0x104), ("link", 0x102)]


def test_program_counter_link_independent_of_load():
    # the link value is pc + step even while a jump/branch target is pending
    actions = [
        {"set": {"load": 1, "next_pc": 0x9000, "compressed": 0}, "link": True},
        {"set": {"load": 1, "next_pc": 0x9000, "compressed": 1}, "link": True},
    ]
    results = _run(_python_device, 0x2000, actions)
    assert results == [("link", 0x2004), ("link", 0x2002)]


@block
def _pc_reset_tb(results):
    comp = ProgramCounter(reset_value=0x1000)
    ports = comp.ports()
    dut = comp.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.reset.next = 0
        yield ports.clk.posedge
        ports.reset.next = 1
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.pc))  # advanced
        ports.reset.next = 0
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.pc))  # reset again mid-run
        raise StopSimulation

    return clkgen, dut, stim


def test_program_counter_reset_midrun():
    results = []
    _pc_reset_tb(results).run_sim()
    assert results == [0x1004, 0x1000]


@block
def _pc_polarity_tb(results, reset_signal):
    comp = ProgramCounter(reset_value=0x40, reset_signal=reset_signal)
    ports = comp.ports()
    dut = comp.hdl(ports)

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        reset_signal.next = 1  # active-high: asserted
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.pc))
        reset_signal.next = 0  # released
        yield ports.clk.posedge
        yield delay(1)
        results.append(int(ports.pc))
        raise StopSimulation

    return clkgen, dut, stim


def test_program_counter_active_high_reset():
    reset_signal = ResetSignal(0, active=1, isasync=False)
    results = []
    _pc_polarity_tb(results, reset_signal).run_sim()
    assert results == [0x40, 0x44]
