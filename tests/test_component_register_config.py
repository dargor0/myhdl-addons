"""Register configuration (``IC-FR-130..137``)."""

from myhdl_addons.components import Register


def test_configuration_matrix():
    for component in (
        Register(fields=(("a", 4), ("b", 8)), en=True, flush=True, load=True),
        Register(fields=(("q", 8),), en=False, reset_enable=False),
    ):
        assert component.hdl(component.ports()) is not None
