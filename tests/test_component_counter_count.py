"""Counter counting behaviour (``IC-FR-080..085``)."""

from myhdl import StopSimulation, always, block, delay, instance

from myhdl_addons.components import Counter


@block
def _python_device(counter, ports):
    return counter.hdl(ports)


@block
def _counter_tb(make_device, results, config, drives, with_tick=False):
    counter = Counter(**config)
    ports = counter.ports()
    dut = make_device(counter, ports)
    tick_sig = ports.signals.get("tick")

    @always(delay(5))
    def clkgen():
        ports.clk.next = not ports.clk

    @instance
    def stim():
        ports.resetn.next = 0
        ports.en.next = 0
        yield ports.clk.posedge
        ports.resetn.next = 1
        for drive in drives:
            for name, value in drive.items():
                getattr(ports, name).next = value
            yield ports.clk.posedge
            yield delay(1)
            if with_tick:
                results.append((int(ports.count), int(tick_sig)))
            else:
                results.append(int(ports.count))
        raise StopSimulation

    return clkgen, dut, stim


def _run(config, drives, with_tick=False, *, make_device=_python_device):
    results = []
    _counter_tb(make_device, results, config, drives, with_tick).run_sim()
    return results


def test_counts_up_and_wraps():
    counts = _run({"width": 4, "max": 3}, [{"en": 1}] * 5)
    assert counts == [1, 2, 3, 0, 1]


def test_step_selection():
    config = {"width": 4, "steps": (1, 2), "max": 15}
    drives = [
        {"en": 1, "step_sel": 0},
        {"en": 1, "step_sel": 1},
        {"en": 1, "step_sel": 0},
    ]
    assert _run(config, drives) == [1, 3, 4]


def test_load_overrides_enable():
    config = {"width": 4, "max": 15, "load_enable": True}
    drives = [
        {"en": 0, "load": 1, "load_value": 7},
        {"en": 1, "load": 0},
    ]
    assert _run(config, drives) == [7, 8]


def test_prescaler_divides_enable():
    config = {"width": 4, "max": 15, "prescaler": 2}
    assert _run(config, [{"en": 1}] * 4) == [0, 1, 1, 2]


def test_saturate_mode():
    config = {"width": 4, "max": 3, "wrap_mode": "saturate"}
    assert _run(config, [{"en": 1}] * 5) == [1, 2, 3, 3, 3]


def test_min_bound_wraps_inside_range():
    config = {"width": 4, "min": 2, "max": 5, "reset_value": 2}
    assert _run(config, [{"en": 1}] * 5) == [3, 4, 5, 2, 3]


def test_tick_on_terminal_count():
    config = {"width": 4, "max": 3, "tick": True}
    assert _run(config, [{"en": 1}] * 4, with_tick=True) == [
        (1, 0),
        (2, 0),
        (3, 1),
        (0, 0),
    ]


def test_saturate_clamps_to_min():
    config = {
        "width": 4,
        "min": 2,
        "max": 5,
        "reset_value": 2,
        "wrap_mode": "saturate",
        "steps": (-1,),
    }
    assert _run(config, [{"en": 1}] * 2) == [2, 2]


def test_down_step_wraps():
    config = {"width": 4, "max": 15, "steps": (-1,)}
    assert _run(config, [{"en": 1}] * 3) == [15, 14, 13]


def test_out_of_range_step_sel_holds():
    config = {"width": 4, "max": 15, "steps": (1, 2, 3)}
    drives = [
        {"en": 1, "step_sel": 0},
        {"en": 1, "step_sel": 3},
        {"en": 1, "step_sel": 1},
    ]
    assert _run(config, drives) == [1, 1, 3]


def test_load_value_above_max_clamps():
    config = {"width": 4, "min": 0, "max": 5, "load_enable": True}
    drives = [
        {"en": 0, "load": 1, "load_value": 10},
        {"en": 1, "load": 0},
    ]
    assert _run(config, drives) == [5, 0]


def test_prescaler_with_load():
    config = {"width": 4, "max": 15, "prescaler": 2, "load_enable": True}
    drives = [
        {"en": 0, "load": 1, "load_value": 7},
        {"en": 1, "load": 0},
        {"en": 1},
    ]
    assert _run(config, drives) == [7, 7, 8]


def test_prescaler_without_load():
    config = {"width": 4, "max": 15, "prescaler": 2, "load_enable": False}
    assert _run(config, [{"en": 1}] * 3) == [0, 1, 1]


def test_load_disabled_holds_when_disabled():
    config = {"width": 4, "max": 15, "load_enable": False}
    drives = [{"en": 1}, {"en": 0}, {"en": 1}]
    assert _run(config, drives) == [1, 1, 2]
