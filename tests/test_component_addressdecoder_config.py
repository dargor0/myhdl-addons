"""AddressDecoder configuration and validation (``IC-FR-089..095``)."""

import pytest

from myhdl_addons.components import AddressDecoder, HdlConfigError


def test_as_dict():
    dec = AddressDecoder(
        adr_width=16,
        windows=((0x0000, 0x100), (0x1000, 0x100)),
        en=True,
        valid=True,
    )
    info = dec.as_dict()
    assert info["adr_width"] == 16
    assert info["windows"] == ((0x0000, 0x100), (0x1000, 0x100))
    assert info["en"] is True
    assert info["valid"] is True
    assert info["registered"] == 0
    assert "AddressDecoder" in repr(dec)


def test_num_windows():
    assert (
        AddressDecoder(adr_width=8, windows=((0, 4), (8, 4), (16, 4))).num_windows == 3
    )


def test_ports_present():
    names = AddressDecoder(adr_width=8, windows=((0, 4),)).ports().names
    assert "adr" in names
    assert "sel0" in names
    assert "clk" not in names
    registered = (
        AddressDecoder(adr_width=8, windows=((0, 4),), registered=1, valid=True)
        .ports()
        .names
    )
    assert {"clk", "reset", "valid"}.issubset(registered)


def test_config_errors_are_early():
    with pytest.raises(HdlConfigError):
        AddressDecoder(adr_width=0, windows=((0, 4),))
    with pytest.raises(HdlConfigError):
        AddressDecoder(adr_width=8, windows=())
    with pytest.raises(HdlConfigError):
        AddressDecoder(adr_width=8)
    with pytest.raises(HdlConfigError):
        AddressDecoder(adr_width=8, windows=((0x10, 0x10), (0x18, 0x10)))
    with pytest.raises(HdlConfigError):
        AddressDecoder(adr_width=8, windows=((0xF0, 0x20),))
    with pytest.raises(HdlConfigError):
        AddressDecoder(adr_width=8, windows=((0,),))


def test_configuration_matrix():
    for component in (
        AddressDecoder(adr_width=8, windows=((0, 4),)),
        AddressDecoder(adr_width=8, windows=((0, 4), (8, 4)), en=True, valid=True),
        AddressDecoder(
            adr_width=16,
            windows=((0x0000, 0x100), (0x1000, 0x100)),
            registered=1,
            en=True,
        ),
    ):
        assert component.hdl(component.ports()) is not None
