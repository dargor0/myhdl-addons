"""PriorityEncoder configuration (``IC-FR-075..078``)."""

from myhdl_addons.components import PriorityEncoder


def test_configuration_matrix():
    component = PriorityEncoder(n=5, priority="high", en=True, registered=1)
    assert component.hdl(component.ports()) is not None
