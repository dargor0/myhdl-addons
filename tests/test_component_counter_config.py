"""Counter configuration and validation (``IC-FR-086..088``)."""

import pytest

from myhdl_addons.components import Counter, HdlConfigError


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        Counter(min=-1)
    with pytest.raises(HdlConfigError):
        Counter(min=5, max=3)
    with pytest.raises(HdlConfigError):
        Counter(width=4, reset_value=99)


def test_configuration_matrix():
    for component in (
        Counter(width=4, max=7),
        Counter(
            width=4,
            steps=(1, 2),
            min=1,
            max=10,
            reset_value=1,
            wrap_mode="saturate",
            prescaler=2,
            tick=False,
            load_enable=False,
        ),
    ):
        assert component.hdl(component.ports()) is not None
