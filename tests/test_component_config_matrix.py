"""Cross-component configuration consistency (``IC-FR-129``).

Per-component configuration-matrix elaboration lives in each component's
``test_component_<component>_config.py``; this file keeps only the checks that
are shared *across* components (uniform parameter names and defaults).
"""

from myhdl_addons.components import (
    WRAP_MODES,
    Counter,
    Incrementer,
    RegisterFile,
)


def test_shared_parameter_names_incrementer_counter():
    inc = Incrementer(steps=(1, -1))
    cnt = Counter(steps=(1, -1))
    for name in ("en", "step_sel", "load", "load_value"):
        assert name in inc.ports().names
        assert name in cnt.ports().names
    assert inc.wrap_mode in WRAP_MODES
    assert cnt.wrap_mode in WRAP_MODES


def test_equivalent_defaults():
    assert Incrementer().width == Counter().width == 32
    assert Incrementer().wrap_mode == Counter().wrap_mode == "wrap"
    assert RegisterFile().read_ports == 2
