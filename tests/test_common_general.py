"""The unified exception hierarchy and shared view in ``myhdl_addons.common``."""

import pytest
from myhdl import Signal, intbv

from myhdl_addons import common
from myhdl_addons.bus_common import BusConfigError as BusConfigErrorAlias
from myhdl_addons.common import (
    AxiConfigError,
    AxiError,
    AxiProtocolError,
    AxiTypeError,
    BusConfigError,
    BusError,
    BusProtocolError,
    BusTypeError,
    ErrorType,
    HdlConfigError,
    HdlError,
    HdlProtocolError,
    HdlTypeError,
    SignalView,
    WishboneConfigError,
    WishboneError,
    WishboneTypeError,
    connect,
)
from myhdl_addons.components import HdlConfigError as HdlConfigErrorAlias
from myhdl_addons.components import SignalView as SignalViewAlias


def test_root_hierarchy():
    assert issubclass(HdlConfigError, HdlError)
    assert issubclass(HdlTypeError, HdlError)
    assert issubclass(HdlProtocolError, HdlError)
    assert issubclass(HdlError, Exception)


def test_bus_layer():
    assert issubclass(BusError, HdlError)
    assert issubclass(BusConfigError, HdlConfigError)
    assert issubclass(BusTypeError, HdlTypeError)
    assert issubclass(BusProtocolError, HdlProtocolError)


def test_protocol_specific_errors():
    assert issubclass(WishboneError, BusError)
    assert issubclass(WishboneConfigError, BusConfigError)
    assert issubclass(WishboneConfigError, WishboneError)
    assert issubclass(WishboneTypeError, BusTypeError)
    assert issubclass(AxiError, BusError)
    assert issubclass(AxiConfigError, BusConfigError)
    assert issubclass(AxiConfigError, AxiError)
    assert issubclass(AxiTypeError, BusTypeError)
    assert issubclass(AxiProtocolError, BusProtocolError)


def test_catchable_at_every_level():
    err = WishboneConfigError("bad config")
    assert isinstance(err, HdlError)
    assert isinstance(err, HdlConfigError)
    assert isinstance(err, BusError)
    assert isinstance(err, BusConfigError)
    assert isinstance(err, WishboneError)


def test_alias_identity_across_packages():
    assert BusConfigErrorAlias is BusConfigError
    assert HdlConfigErrorAlias is HdlConfigError
    assert SignalViewAlias is SignalView


def test_error_type_alias():
    assert ErrorType == type[HdlError]
    assert ErrorType.__origin__ is type


def test_signal_view_is_shared():
    view = SignalView(a=Signal(intbv(0)[4:]), y=Signal(intbv(0)[4:]))
    assert view.a is view["a"]
    assert view.names == ["a", "y"]
    assert common.SignalView is SignalView
    assert callable(connect)


def test_signal_view_rejects_non_signals():
    sig = Signal(intbv(0)[4:])
    with pytest.raises(HdlTypeError):
        SignalView(x=5)
    with pytest.raises(HdlTypeError):
        SignalView(items=[sig, 5])
    view = SignalView(a=sig)
    with pytest.raises(HdlTypeError):
        view.b = 5
    with pytest.raises(HdlTypeError):
        view.a = "nope"


def test_signal_view_sequence_members_are_tuples():
    a, b = Signal(intbv(0)[4:]), Signal(intbv(0)[4:])
    view = SignalView(items=[a, b])
    assert view.items == (a, b)
    assert isinstance(view.items, tuple)


def test_signal_view_is_mutable():
    a, b = Signal(intbv(0)[4:]), Signal(intbv(0)[4:])
    view = SignalView(a=a)
    view.a = b
    assert view.a is b
    view.c = a
    assert "c" in view
    assert view.names == ["a", "c"]
    del view.c
    assert view.names == ["a"]
    with pytest.raises(KeyError):
        view["missing"]
