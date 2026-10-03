"""Decoder configuration (``IC-FR-070..074``)."""

from myhdl_addons.components import Decoder


def test_configuration_matrix():
    component = Decoder(n=3, en=True, registered=1)
    assert component.hdl(component.ports()) is not None
